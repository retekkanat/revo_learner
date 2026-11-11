"""Save model-call records, application decisions and exercise evidence.

The ledger records each AWS call attempt, including failures, retries,
timeouts and interruptions. It calculates model cost from the returned token
usage and the dated prices in `data/pricing.json`. If the service reports no
usage, the ledger records the cost as unknown.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import config

STATUSES = ("succeeded", "rejected", "interrupted", "failed", "timed_out")


def utc_now() -> str:
    """Return the current time as an ISO 8601 UTC instant."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    """Return a short random identifier for a run or a call.

    It always starts with a letter, so it can never look like an account number.
    """
    return "r" + uuid.uuid4().hex[:11]


def input_digest(value: object) -> str:
    """Return a SHA-256 digest of a value, so a log can name an input without holding it."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- prices


@dataclass(frozen=True)
class Prices:
    """Dated prices in US dollars, read from `pricing.json`."""

    read_on: str
    per_million: dict[str, dict]
    retrieve_per_1000: float | None = None
    agentic_per_1000: float | None = None

    def model(self, model_id: str) -> dict | None:
        return self.per_million.get(model_id)


def load_prices(path: Path | None = None) -> Prices:
    """Read the dated prices used for cost calculations from the price register."""
    data = json.loads((path or config.DATA_DIR / "pricing.json").read_text(encoding="utf-8"))
    models = {row["inference_profile_id"]: row for row in data.get("models", [])}
    knowledge_bases = data.get("managed_knowledge_bases") or {}

    def price(key: str) -> float | None:
        return float(knowledge_bases[key]) if knowledge_bases.get(key) is not None else None

    return Prices(read_on=data["source"]["read_on"], per_million=models,
                  retrieve_per_1000=price("retrieve_per_1000_requests"),
                  agentic_per_1000=price("agentic_retrieve_per_1000_requests"))


def model_cost(prices: Prices, model_id: str, usage: dict | None) -> tuple[float | None, str]:
    """Return the calculated model-call cost and its status.

    Bedrock counts only uncached input in `inputTokens`; cache reads and writes are
    priced separately. With no usage block the cost is unknown.
    """
    if not usage:
        return None, "unknown_usage"
    row = prices.model(model_id)
    if row is None:
        return None, "no_price"
    cost = (
        usage.get("inputTokens", 0) * row["input"]
        + usage.get("outputTokens", 0) * row["output"]
        + usage.get("cacheReadInputTokens", 0) * (row.get("cache_read") or 0)
        + usage.get("cacheWriteInputTokens", 0) * (row.get("cache_write_5m") or 0)
    ) / 1_000_000
    return round(cost, 8), "calculated"


def agentic_cost(prices: Prices) -> tuple[float | None, str]:
    """Return the price of one agentic retrieval call.

    The call also makes `Retrieve` calls underneath, which are priced separately
    and whose number the response does not report, so the cost is `partial`.
    """
    if prices.agentic_per_1000 is None:
        return None, "no_price"
    return round(prices.agentic_per_1000 / 1000, 8), "partial"


def retrieve_cost(prices: Prices, requests: int = 1) -> tuple[float | None, str]:
    """Return the cost of `Retrieve` calls, if the price register holds that price."""
    if prices.retrieve_per_1000 is None:
        return None, "no_price"
    return round(prices.retrieve_per_1000 * requests / 1000, 8), "calculated"


# --------------------------------------------------------------------------- ledger


class Ledger:
    """Append one JSON line for every attempt to call AWS."""

    def __init__(self, path: Path | None = None, prices: Prices | None = None) -> None:
        self.path = path or config.LEDGER_FILE
        self.prices = prices or load_prices()

    def record(self, *, operation: str, status: str, model_id: str | None = None,
               usage: dict | None = None, **fields: object) -> dict:
        """Write and return a ledger row, leaving usage and cost unset when usage is unknown."""
        if status not in STATUSES:
            raise ValueError(f"unknown ledger status {status!r}")
        if operation == "retrieve" and status == "succeeded":
            cost, cost_status = retrieve_cost(self.prices)
        elif operation == "agentic_retrieve" and status == "succeeded":
            cost, cost_status = agentic_cost(self.prices)
        elif model_id:
            cost, cost_status = model_cost(self.prices, model_id, usage)
        else:
            cost, cost_status = None, "unknown_usage"
        row = {
            "ts": utc_now(),
            "call_id": new_id(),
            "operation": operation,
            "model_id": model_id,
            "region": fields.pop("region", None) or config.region(),
            "status": status,
            "attempt": fields.pop("attempt", 1),
            "run_id": fields.pop("run_id", None),
            "request_id": fields.pop("request_id", None),
            "stop_reason": fields.pop("stop_reason", None),
            "error_code": fields.pop("error_code", None),
            "http_status": fields.pop("http_status", None),
            "will_retry": fields.pop("will_retry", False),
            "usage_known": bool(usage),
            "input_tokens": (usage or {}).get("inputTokens"),
            "output_tokens": (usage or {}).get("outputTokens"),
            "cache_read_input_tokens": (usage or {}).get("cacheReadInputTokens"),
            "cache_write_input_tokens": (usage or {}).get("cacheWriteInputTokens"),
            "latency_ms": fields.pop("latency_ms", None),
            "elapsed_ms": fields.pop("elapsed_ms", None),
            "cost_usd": cost,
            "cost_status": cost_status,
            "price_read_on": self.prices.read_on,
            "note": fields.pop("note", None),
        }
        if fields:
            row["detail"] = fields
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def rows(self, run_id: str | None = None) -> list[dict]:
        """Return every row, or the rows of one run."""
        if not self.path.is_file():
            return []
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [row for row in rows if run_id is None or row.get("run_id") == run_id]

    def totals(self, run_id: str | None = None) -> dict:
        """Summarise the rows: attempts by status, tokens, and the known and unknown costs."""
        rows = self.rows(run_id)
        by_status: dict[str, int] = {}
        for row in rows:
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        known = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
        return {
            "attempts": len(rows),
            "by_status": by_status,
            "input_tokens": sum(row["input_tokens"] or 0 for row in rows),
            "output_tokens": sum(row["output_tokens"] or 0 for row in rows),
            "known_cost_usd": round(sum(known), 6),
            "attempts_with_unknown_cost": len(rows) - len(known),
            "price_read_on": self.prices.read_on,
        }


# ----------------------------------------------------------------------- decisions


class RunLog:
    """Append one JSON line for every decision the application takes about a request."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.RUN_LOG_FILE

    def decision(self, *, run_id: str, rule: str, decision: str, reason: str,
                 tool: str | None = None, input_value: object = None, **extra: object) -> dict:
        """Write one decision line. The input appears only as a digest."""
        line = {
            "ts": utc_now(),
            "run_id": run_id,
            "rule": rule,
            "tool": tool,
            "input_digest": input_digest(input_value) if input_value is not None else None,
            "decision": decision,
            "reason": reason,
        }
        line.update(extra)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        return line

    def lines(self, run_id: str | None = None) -> list[dict]:
        if not self.path.is_file():
            return []
        lines = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [line for line in lines if run_id is None or line.get("run_id") == run_id]


# ------------------------------------------------------------------------ evidence

SECRET_PATTERNS = {
    "account number": config.ACCOUNT_NUMBER,
    "access key identifier": config.ACCESS_KEY_ID,
}


def screen(text: str) -> list[str]:
    """Return the kinds of secret that a text contains, without repeating them."""
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


@dataclass
class EvidenceFolder:
    """The learner's evidence folder, `work/evidence/<owner>/`."""

    root: Path = field(default_factory=lambda: config.WORK_DIR / "evidence" / config.owner())

    def write(self, name: str, data: object) -> Path:
        """Write one JSON evidence record, redacted, and return its path."""
        text = config.redact(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / name
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def read(self, name: str) -> object:
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def start_index(self, template: Path | None = None) -> Path:
        """Copy the evidence-pack template to `INDEX.md` once, and never overwrite it."""
        index = self.root / "INDEX.md"
        if not index.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template or config.LABS_DIR / "evidence-pack-template.md", index)
        return index

    def freeze(self) -> dict:
        """Copy the records into a dated, checksummed folder that is not edited again."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        frozen = self.root / f"frozen-{stamp}"
        frozen.mkdir(parents=True, exist_ok=False)
        sources = sorted(path for path in self.root.iterdir() if path.is_file())
        sources += [path for path in (config.LEDGER_FILE, config.RUN_LOG_FILE) if path.is_file()]
        files = {}
        for path in sources:
            target = frozen / path.name
            shutil.copyfile(path, target)
            files[path.name] = file_sha256(target)
        manifest = {"frozen_at": utc_now(), "files": files}
        findings = {name: screen((frozen / name).read_text(encoding="utf-8")) for name in files}
        manifest["secret_findings"] = {name: kinds for name, kinds in findings.items() if kinds}
        (frozen / "FROZEN.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            shown = str(frozen.relative_to(config.LABS_DIR))
        except ValueError:
            shown = str(frozen)
        return {"folder": shown, **manifest}


def wait_ms(started: float) -> int:
    """Return the milliseconds since `started`, a `time.perf_counter()` value."""
    return int((time.perf_counter() - started) * 1000)
