"""Validate and load Kestrel documents and case records for Exercise 4.

The ingestion plan checks each record against contract version 1.0 before any
AWS write. Invalid records are saved with their validation errors. Accepted
records use stable keys and content checksums so unchanged input is not written
again. Manifest entries record the source and checksum of each loaded record.

The bucket contains raw source files in `raw/`, validated records in
`cleansed/`, knowledge base inputs in `curated/`, and rejected records in
`rejected/`.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from botocore.exceptions import ClientError
from pydantic import ValidationError

from . import config
from .ledger import utc_now
from .schemas import CONTRACT_VERSION, CaseRecord, DocumentMetadata

ZONES = ("raw/", "cleansed/", "curated/", "rejected/")
DOCUMENT_PREFIX = "curated/documents/"
# The managed S3 connector reads each document's metadata file from this prefix, under
# the document's full key: `curated/metadata/curated/documents/<file>.metadata.json`.
# This layout ingested on 31 October 2026; a file beside its document did not.
METADATA_PREFIX = "curated/metadata/"
DOCUMENT_SUFFIXES = (".md",)
HEADER_FIELDS = {"Last reviewed": "last_reviewed", "Document id": "doc_id", "Owner team": "owner_team",
                 "Audience": "audience", "Status": "status"}


class WaitTimeout(RuntimeError):
    """Polling did not finish before the configured timeout."""


def wait_for(check: Callable[[], tuple[bool, object]], *, timeout: float, interval: float, what: str,
             sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> object:
    """Poll `check` until it reports done, or raise `WaitTimeout` when the limit passes."""
    deadline = clock() + timeout
    while True:
        done, value = check()
        if done:
            return value
        if clock() + interval > deadline:
            state = value.get("status", "unknown") if isinstance(value, dict) else value
            raise WaitTimeout(f"{what} did not finish within {timeout:.0f} seconds; last state: {state}")
        sleep(interval)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------- contract checks


def contract_problems(error: ValidationError) -> list[str]:
    """Turn a validation error into one short reason for each broken rule."""
    reasons = []
    for item in error.errors():
        where = ".".join(str(part) for part in item["loc"]) or "record"
        message = item["msg"].removeprefix("Value error, ")
        reasons.append(f"{where}: {message}")
    return reasons


def validate_case(record: object) -> list[str]:
    """Return every contract rule that a case record breaks, or an empty list."""
    if not isinstance(record, dict):
        return ["record: is not a JSON object"]
    try:
        CaseRecord.model_validate(record)
    except ValidationError as error:
        return contract_problems(error)
    return []


@dataclass
class ParsedDocument:
    """One source document, its header as metadata, and its checksum."""

    source: str
    file_name: str
    metadata: DocumentMetadata
    data: bytes
    sha256: str
    fresh: bool


def parse_header(text: str) -> dict:
    """Read the title line and the five header lines at the top of a document."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("header: the first line is not a `# <title>` line")
    values = {"title": lines[0][2:].strip()}
    for line in lines[1:12]:
        name, separator, value = line.partition(":")
        if separator and name.strip() in HEADER_FIELDS:
            values[HEADER_FIELDS[name.strip()]] = value.strip()
    return values


def parse_document(path: Path, reference: date) -> tuple[ParsedDocument | None, list[str]]:
    """Check one document file against the contract. Return it, or the rules it breaks."""
    source = relative_source(path)
    if path.suffix not in DOCUMENT_SUFFIXES:
        return None, [f"file type: {path.suffix or 'none'} is not a supported document type (.md)"]
    data = path.read_bytes()
    try:
        header = parse_header(data.decode("utf-8"))
        metadata = DocumentMetadata.model_validate(header)
    except UnicodeDecodeError:
        return None, ["encoding: the file is not UTF-8 text"]
    except ValueError as error:
        if isinstance(error, ValidationError):
            return None, contract_problems(error)
        return None, [str(error)]
    expected_id = path.name[:5].replace("-", "_")
    if metadata.doc_id != expected_id:
        return None, [f"doc_id: {metadata.doc_id} does not match the file name {path.name}"]
    age = (reference - metadata.last_reviewed).days
    return ParsedDocument(source, path.name, metadata, data, sha256_bytes(data),
                          fresh=0 <= age <= config.FRESHNESS_DAYS), []


def relative_source(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.LABS_DIR))
    except ValueError:
        return path.name


# ------------------------------------------------------------------------ the plan


@dataclass
class Rejected:
    """A record that broke the contract, the rules it broke and where it came from."""

    kind: str
    source: str
    identifier: str
    position: int | None
    reasons: list[str]
    record: object


@dataclass
class IngestionPlan:
    """What a run would write and reject, decided before anything is written."""

    cases: list[dict] = field(default_factory=list)
    case_sources: dict[str, dict] = field(default_factory=dict)
    documents: list[ParsedDocument] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    duplicates: list[dict] = field(default_factory=list)
    read: dict[str, int] = field(default_factory=lambda: {"cases": 0, "documents": 0})
    raw_files: list[Path] = field(default_factory=list)


def plan_ingestion(case_files: list[Path], document_files: list[Path], reference: date) -> IngestionPlan:
    """Validate every source record and plan its destination. This step calls no AWS service."""
    plan = IngestionPlan(raw_files=[*case_files, *document_files])
    seen: dict[str, bytes] = {}
    for case_file in case_files:
        data = json.loads(case_file.read_text(encoding="utf-8"))
        version = data.get("dataset_version", "unknown")
        for position, record in enumerate(data.get("cases", []), start=1):
            plan.read["cases"] += 1
            identifier = record.get("case_id", f"record {position}") if isinstance(record, dict) else f"record {position}"
            reasons = validate_case(record)
            if reasons:
                plan.rejected.append(Rejected("case", relative_source(case_file), str(identifier), position,
                                              reasons, record))
                continue
            content = canonical_json(record)
            if identifier in seen:
                identical = seen[identifier] == content
                plan.duplicates.append({"case_id": identifier, "source": relative_source(case_file),
                                        "position": position, "identical": identical})
                if not identical:
                    plan.rejected.append(Rejected("case", relative_source(case_file), identifier, position,
                                                  ["case_id: a second record with this key has different "
                                                   "content; a person must decide which is right"], record))
                continue
            seen[identifier] = content
            plan.cases.append(record)
            plan.case_sources[identifier] = {"source": relative_source(case_file), "source_version": version,
                                             "position": position, "sha256": sha256_bytes(content)}
    for document_file in document_files:
        plan.read["documents"] += 1
        parsed, reasons = parse_document(document_file, reference)
        if parsed is None:
            plan.rejected.append(Rejected("document", relative_source(document_file), document_file.name,
                                          None, reasons, None))
        else:
            plan.documents.append(parsed)
    return plan


def dataset_sources() -> tuple[list[Path], list[Path]]:
    """Return the Kestrel case file and document files from `data/`."""
    return [config.DATA_DIR / "cases.json"], sorted((config.DATA_DIR / "documents").glob("*"))


def fixture_sources() -> tuple[list[Path], list[Path]]:
    """Return the contract-test fixtures: records built to break each rule once."""
    folder = config.FIXTURES_DIR / "contract-tests"
    return sorted(folder.glob("*.json")), sorted((folder / "documents").glob("*"))


def quality_report(plan: IngestionPlan, writes: dict | None = None) -> dict:
    """Count accepted and rejected records by reason, with duplicates, missing values and stale documents."""
    by_reason: dict[str, int] = {}
    for rejected in plan.rejected:
        for reason in rejected.reasons:
            rule = reason.split(":", 1)[0]
            by_reason[rule] = by_reason.get(rule, 0) + 1
    missing: dict[str, int] = {}
    for rejected in plan.rejected:
        for reason in rejected.reasons:
            if reason.endswith("Field required"):
                field_name = reason.split(":", 1)[0]
                missing[field_name] = missing.get(field_name, 0) + 1
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": utc_now(),
        "read": plan.read,
        "accepted": {"cases": len(plan.cases), "documents": len(plan.documents)},
        "rejected": {"total": len(plan.rejected), "by_rule": by_reason,
                     "records": [{"kind": item.kind, "source": item.source, "identifier": item.identifier,
                                  "position": item.position, "reasons": item.reasons} for item in plan.rejected]},
        "duplicates": plan.duplicates,
        "missing_required_values": missing,
        "stale_documents": [{"doc_id": doc.metadata.doc_id, "last_reviewed": doc.metadata.last_reviewed.isoformat(),
                             "status": doc.metadata.status} for doc in plan.documents if not doc.fresh],
        "documents_by_status": {status: sum(doc.metadata.status == status for doc in plan.documents)
                                for status in ("current", "superseded")},
        "writes": writes or {},
    }


# ------------------------------------------------------------------- AWS writes


def metadata_sidecar(document: ParsedDocument) -> bytes:
    """Convert document header fields to a `.metadata.json` record for the S3 connector."""
    meta = document.metadata

    def text(value: str) -> dict:
        return {"value": {"type": "STRING", "stringValue": value}}

    attributes = {
        "doc_id": text(meta.doc_id),
        "title": text(meta.title),
        "owner_team": text(meta.owner_team),
        "audience": text(meta.audience),
        "status": text(meta.status),
        "last_reviewed": {"value": {"type": "NUMBER", "numberValue": int(meta.last_reviewed.strftime("%Y%m%d"))}},
        "contract_version": text(CONTRACT_VERSION),
        "source_sha256": text(document.sha256),
    }
    return canonical_json({"metadataAttributes": attributes})


def ensure_bucket(s3, name: str, lab: int = 4) -> bool:
    """Create the private, tagged ingestion bucket in the configured Region, once."""
    try:
        s3.head_bucket(Bucket=name)
        return False
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
            raise
    region = config.region()
    arguments = {"Bucket": name}
    if region != "us-east-1":
        arguments["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**arguments)
    s3.get_waiter("bucket_exists").wait(Bucket=name, WaiterConfig={"Delay": 2, "MaxAttempts": 30})
    s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_tagging(Bucket=name, Tagging={"TagSet": config.tag_list(lab)})
    return True


def ensure_table(dynamodb, name: str, lab: int = 4) -> bool:
    """Create the on-demand, tagged case table keyed on `case_id`, once, and wait for it with a limit."""
    try:
        dynamodb.describe_table(TableName=name)
        created = False
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        dynamodb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                              AttributeDefinitions=[{"AttributeName": "case_id", "AttributeType": "S"}],
                              KeySchema=[{"AttributeName": "case_id", "KeyType": "HASH"}],
                              Tags=config.tag_list(lab))
        created = True
    wait_for(lambda: (dynamodb.describe_table(TableName=name)["Table"]["TableStatus"] == "ACTIVE", "CREATING"),
             timeout=120, interval=3, what=f"table {name}")
    return created


def put_object_if_changed(s3, bucket: str, key: str, data: bytes, *, content_type: str = "text/markdown") -> tuple[str, str]:
    """Write an object only if its checksum differs. Return the outcome and when it was first written."""
    checksum = sha256_bytes(data)
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        if head["Metadata"].get("sha256") == checksum:
            return "unchanged", head["Metadata"].get("ingested-at", "")
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
            raise
    written_at = utc_now()
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type,
                  Metadata={"sha256": checksum, "ingested-at": written_at, "contract-version": CONTRACT_VERSION})
    return "written", written_at


def put_case_if_changed(dynamodb, table: str, record: dict, source: dict) -> tuple[str, str]:
    """Write a case keyed on `case_id` only if it is new or its content changed.

    The condition makes the write idempotent: a second run with the same record
    fails the condition, which the code counts as unchanged, not as an error.
    """
    written_at = utc_now()
    try:
        dynamodb.put_item(
            TableName=table,
            Item={
                "case_id": {"S": record["case_id"]},
                "owner_team": {"S": record["owner_team"]},
                "customer_id": {"S": record["customer_id"]},
                "status": {"S": record["status"]},
                "record": {"S": json.dumps(record, ensure_ascii=False)},
                "content_sha256": {"S": source["sha256"]},
                "contract_version": {"S": CONTRACT_VERSION},
                "source": {"S": f"{source['source']}#{source['position']}"},
                "source_version": {"S": source["source_version"]},
                "ingested_at": {"S": written_at},
            },
            ConditionExpression="attribute_not_exists(case_id) OR content_sha256 <> :sha",
            ExpressionAttributeValues={":sha": {"S": source["sha256"]}},
            ReturnValuesOnConditionCheckFailure="ALL_OLD",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return "unchanged", error.response.get("Item", {}).get("ingested_at", {}).get("S", "")
    return "written", written_at


def ingest(plan: IngestionPlan, *, s3, dynamodb, bucket: str, table: str) -> tuple[list[dict], dict]:
    """Write the plan to the four zones and the table. Return the manifest rows and the write counts."""
    writes = {zone.rstrip("/"): {"written": 0, "unchanged": 0} for zone in ZONES}
    writes["table"] = {"written": 0, "unchanged": 0}
    manifest: list[dict] = []

    def put(key: str, data: bytes, content_type: str = "text/markdown") -> str:
        outcome, written_at = put_object_if_changed(s3, bucket, key, data, content_type=content_type)
        writes[key.split("/", 1)[0]][outcome] += 1
        return written_at

    for path in plan.raw_files:
        put(f"raw/{relative_source(path).removeprefix('data/')}", path.read_bytes(),
            "application/json" if path.suffix == ".json" else "text/markdown")
    for record in plan.cases:
        source = plan.case_sources[record["case_id"]]
        put(f"cleansed/cases/{record['case_id']}.json", canonical_json(record), "application/json")
        outcome, written_at = put_case_if_changed(dynamodb, table, record, source)
        writes["table"][outcome] += 1
        manifest.append({"kind": "case", "id": record["case_id"], "source": source["source"],
                         "source_version": source["source_version"], "sha256": source["sha256"],
                         "contract_version": CONTRACT_VERSION, "location": f"dynamodb://{table}/{record['case_id']}",
                         "ingested_at": written_at, "status": record["status"]})
    for document in plan.documents:
        put(f"cleansed/documents/{document.file_name}", document.data)
        key = f"{DOCUMENT_PREFIX}{document.file_name}"
        written_at = put(key, document.data)
        put(f"{METADATA_PREFIX}{key}.metadata.json", metadata_sidecar(document), "application/json")
        manifest.append({"kind": "document", "id": document.metadata.doc_id, "source": document.source,
                         "source_version": document.metadata.last_reviewed.isoformat(),
                         "sha256": document.sha256, "contract_version": CONTRACT_VERSION,
                         "location": f"s3://{bucket}/{key}", "ingested_at": written_at,
                         "status": document.metadata.status, "audience": document.metadata.audience,
                         "fresh": document.fresh})
    for index, rejected in enumerate(plan.rejected, start=1):
        put(f"rejected/{rejected.kind}s/{index:03d}-{rejected.identifier.replace(' ', '-')}.json",
            canonical_json({"source": rejected.source, "position": rejected.position, "reasons": rejected.reasons,
                            "contract_version": CONTRACT_VERSION, "record": rejected.record}), "application/json")
    manifest.sort(key=lambda row: (row["kind"], row["id"]))
    put("curated/manifest.json", canonical_json(manifest), "application/json")
    return manifest, writes


def save_lab4_outputs(manifest: list[dict], report: dict) -> Path:
    """Keep the manifest and the quality report in `work/lab4/` with the Exercise 4 records."""
    folder = config.WORK_DIR / "lab4"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "quality-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
    return folder


def load_manifest(path: Path | None = None) -> dict[str, dict]:
    """Return the manifest rows of documents, by document identifier."""
    rows = json.loads((path or config.WORK_DIR / "lab4" / "manifest.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows if row["kind"] == "document"}
