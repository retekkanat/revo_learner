"""Shared Region, model, resource-name and execution-limit settings.

The package reads the Region from environment variables and the course model
identifier from MODEL_ID. Boto3 and the AWS CLI obtain credentials from their
configured sources; this module stores no credentials.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import string
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Use the EU geographic inference profile to process Kestrel's data in Europe.
# Its seven destination Regions include London, which is outside the European Union.
# Checked with `aws bedrock get-inference-profile` on 31 October 2026.
MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
# The base model identifier, used only for the availability and lifecycle checks.
# On-demand requests using this identifier in London require an inference profile instead.
BASE_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_CHOICE_REASON = (
    "The EU geographic inference profile sends every call to one of seven European AWS Regions, "
    "which keeps Kestrel's data in Europe as its rules require; a global profile could route to any "
    "commercial Region."
)
# The model that the Exercise 2 extension compares with the course model. It was Active on
# 31 October 2026 (from `aws bedrock get-foundation-model`), and `data/pricing.json`
# prices it, so the comparison's cost column is complete.
COMPARISON_MODEL_ID = "eu.anthropic.claude-sonnet-4-6"

# The learner policy permits course resources in these two Regions. Normal lab
# operations use config.region(); teardown checks tagged resources in both.
POLICY_REGIONS = ("eu-west-2", "us-east-1")

# Model call settings.
MAX_TOKENS = 700
TEMPERATURE = 0.0
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 60
# AWS advises a longer read timeout for native structured output, because the first
# call with a new schema can take longer while Bedrock prepares it.
STRUCTURED_OUTPUT_READ_TIMEOUT_SECONDS = 120
# Retry settings for temporary errors. MAX_ATTEMPTS counts the first try.
# A new account's quota for the course model can be as low as 10 requests a minute
# (the authoring account's was, on 31 October 2026), so a throttle can last several
# seconds. Six attempts with full-jitter waits of up to 2, 4, 8, 16 and 32 seconds
# give the service time to recover while limiting the total number of attempts.
MAX_ATTEMPTS = 6
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 32.0

# Limits of the tool loop. The loop counts model calls, not tool calls, and checks
# both limits before every model call.
MAX_MODEL_CALLS = 6
RUN_DEADLINE_SECONDS = 180.0

# Retrieval settings. TOP_K is the measure of Exercise 5, part one: does the
# supporting document appear in the top five results? Week 2 adds a relevance
# threshold, the caller's document filter and the register of documents that
# disagree; until then the assistant answers from the top passages it retrieves.
TOP_K = 5

# Timeouts and polling intervals for knowledge base creation, ingestion and deletion.
KB_WAIT_SECONDS = 900.0
INGESTION_WAIT_SECONDS = 600.0
POLL_INTERVAL_SECONDS = 10.0

# Documents more than this many days older than the dataset's reference date fail
# the freshness check.
FRESHNESS_DAYS = 365

# Paths. The lab folder is the nearest folder above the package that holds the
# dataset, so the package runs from `starter/`, from the supplied version of an
# exercise in `starter/exercise-<n>/`, or from `reference/`.


def _lab_folder() -> Path:
    here = Path(__file__).resolve()
    for folder in here.parents:
        if (folder / "data" / "cases.json").is_file():
            return folder
    return here.parents[2]


LABS_DIR = _lab_folder()
DATA_DIR = LABS_DIR / "data"
WORK_DIR = LABS_DIR / "work"
FIXTURES_DIR = LABS_DIR / "fixtures"
STATE_FILE = WORK_DIR / "state.json"
LEDGER_FILE = WORK_DIR / "calls.jsonl"
RUN_LOG_FILE = WORK_DIR / "runlog.jsonl"

OWNER_PATTERN = re.compile(r"^[a-z]{2,4}$")
COURSE_TAG = "fde-aws"


class ConfigurationError(RuntimeError):
    """The environment is missing a setting that the lab needs."""


def region() -> str:
    """Return the AWS Region from the environment, or explain how to set it."""
    value = (os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "").strip()
    if not value:
        raise ConfigurationError(
            "AWS_DEFAULT_REGION is not set. Run `export AWS_DEFAULT_REGION=eu-west-2` "
            "in the shell that starts Jupyter, then restart the kernel."
        )
    return value


def owner() -> str:
    """Return the learner's initials, which name and tag every resource."""
    value = os.environ.get("FDE_OWNER", "").strip().lower()
    if not OWNER_PATTERN.fullmatch(value):
        raise ConfigurationError(
            "FDE_OWNER must hold your initials, two to four lower-case letters. "
            "Run `export FDE_OWNER=<initials>` in the shell that starts Jupyter."
        )
    return value


def tags(lab: int) -> dict[str, str]:
    """Return the three tags that every course resource carries."""
    return {"course": COURSE_TAG, "lab": str(lab), "owner": owner()}


def tag_list(lab: int) -> list[dict[str, str]]:
    """Return the tags in the Key and Value form that S3 and DynamoDB expect."""
    return [{"Key": key, "Value": value} for key, value in tags(lab).items()]


def reference_date() -> date:
    """Return the date that the dataset describes, from `cases.json`."""
    data = json.loads((DATA_DIR / "cases.json").read_text(encoding="utf-8"))
    return date.fromisoformat(data["reference_date"])


def random_suffix(length: int = 6) -> str:
    """Return lower-case letters for a globally unique bucket name."""
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))


# --------------------------------------------------------------------------- state


def load_state() -> dict:
    """Return the names and identifiers of the resources this lab created."""
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    """Record resource names and identifiers so later days and teardown find them."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ResourceNames:
    """The names of the resources that Exercises 4 and 5 create for one learner."""

    bucket: str
    table: str
    role: str
    knowledge_base: str
    data_source: str
    prompt: str


def resource_names() -> ResourceNames:
    """Return stable resource names, creating the bucket suffix once."""
    state = load_state()
    suffix = state.get("bucket_suffix")
    if not suffix:
        suffix = random_suffix()
        state["bucket_suffix"] = suffix
        save_state(state)
    who = owner()
    return ResourceNames(
        bucket=f"fde-{who}-kestrel-{suffix}",
        table=f"fde-{who}-kestrel-cases",
        role=f"fde-{who}-kestrel-kb-role",
        knowledge_base=f"fde-{who}-kestrel-kb",
        data_source=f"fde-{who}-kestrel-documents",
        prompt=f"fde-{who}-kestrel-assistant",
    )


# ------------------------------------------------------------------ the AWS CLI

# An account number stands alone: in an ARN it sits between colons, and in JSON or a
# message between quotes or spaces. Twelve digits joined to letters, digits, underscores
# or hyphens are part of something else, such as a request identifier or a digest.
ACCOUNT_NUMBER = re.compile(r"(?<![\w-])\d{12}(?![\w-])")
ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


def redact(text: str) -> str:
    """Replace account numbers and access key identifiers before anything is shown."""
    return ACCESS_KEY_ID.sub("<access-key-id>", ACCOUNT_NUMBER.sub("<account-id>", text))


@dataclass(frozen=True)
class CliResult:
    """One AWS CLI command and its redacted result."""

    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def error_code(self) -> str | None:
        """Return the AWS error code in the message, such as `AccessDeniedException`."""
        match = re.search(r"\(([A-Za-z]+(?:Exception|Error|Denied)?)\)", self.stderr)
        return match.group(1) if match else None

    def as_record(self) -> dict:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "error_code": self.error_code,
            "stdout": self.stdout.strip(),
            "stderr": self.stderr.strip(),
        }


def aws_cli(arguments: list[str], *, env: dict[str, str] | None = None, timeout: float = 60) -> CliResult:
    """Run one AWS CLI command and return its output with every account number redacted.

    The command is shown and recorded as typed, so a reader can repeat it. The
    result never holds an account number or an access key identifier.
    """
    executable = shutil.which("aws")
    if executable is None:
        raise ConfigurationError("The AWS CLI is not on PATH. Install it as the pre-work describes.")
    completed = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    return CliResult(
        command=redact("aws " + " ".join(arguments)),
        returncode=completed.returncode,
        stdout=redact(completed.stdout),
        stderr=redact(completed.stderr),
    )


@dataclass(frozen=True)
class IdentityRecord:
    """The parts of a caller ARN that the Exercise 1 identity record explains."""

    partition: str
    service: str
    account: str
    principal_kind: str
    principal_name: str
    session_name: str | None

    def as_record(self) -> dict:
        return {
            "partition": self.partition,
            "service": self.service,
            "account": self.account,
            "principal_kind": self.principal_kind,
            "principal_name": self.principal_name,
            "session_name": self.session_name,
        }


def describe_identity(arn: str) -> IdentityRecord:
    """Split a caller ARN into its parts, with the account number replaced.

    `arn:aws:iam::<account-id>:user/<name>` is an IAM user.
    `arn:aws:sts::<account-id>:assumed-role/<role>/<session>` is an assumed role,
    which is also how an IAM Identity Center session reaches the account.
    """
    parts = redact(arn.strip()).split(":", 5)
    if len(parts) != 6 or parts[0] != "arn":
        raise ValueError("The text is not an ARN.")
    _, partition, service, _, account, resource = parts
    kind, _, rest = resource.partition("/")
    if kind == "assumed-role":
        role, _, session = rest.partition("/")
        return IdentityRecord(partition, service, account, "assumed-role", role, session or None)
    if kind == "user":
        return IdentityRecord(partition, service, account, "user", rest.split("/")[-1], None)
    if kind == "root":
        return IdentityRecord(partition, service, account, "root", "root", None)
    return IdentityRecord(partition, service, account, kind, rest, None)
