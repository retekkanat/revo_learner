"""Exercise 4 check: the data contract, ingestion, the manifest and the quality report.

Run from the lab folder:  uv run --directory starter/exercise-4 python -m pytest ../checks/check_exercise_4.py
The code checks always run. The record checks run when KESTREL_EVIDENCE names
your records folder, as the workbook's check cell sets it.
"""

from __future__ import annotations

import hashlib
import json

from kestrel_doubles import FakeDynamo
from kestrel_evidence import read_json, work_folder

from support_assistant import config, ingest


def fixture_report():
    return ingest.quality_report(ingest.plan_ingestion(*ingest.fixture_sources(), config.reference_date()))


def test_validate_case_returns_every_broken_rule():
    report = fixture_report()
    rules = set(report["rejected"]["by_rule"])
    assert {"summary", "plan", "opened_at", "priority"} <= rules
    assert report["accepted"]["cases"] == 1


def test_a_valid_dataset_record_passes_the_contract():
    record = json.loads((config.DATA_DIR / "cases.json").read_text(encoding="utf-8"))["cases"][0]
    assert ingest.validate_case(record) == []
    assert ingest.validate_case("not a record") == ["record: is not a JSON object"]


def test_the_case_write_is_idempotent():
    record = {"case_id": "case_9001", "owner_team": "billing", "customer_id": "cust_9001", "status": "open"}
    source = {"source": "fixtures/x.json", "position": 1, "source_version": "1.0", "sha256": "abc"}
    table = FakeDynamo()
    first = ingest.put_case_if_changed(table, "t", record, source)
    second = ingest.put_case_if_changed(table, "t", record, source)
    assert first[0] == "written" and second == ("unchanged", first[1]) and table.writes == 1
    changed = ingest.put_case_if_changed(table, "t", record, dict(source, sha256="def"))
    assert changed[0] == "written" and table.writes == 2


def test_evidence_manifest_and_quality_report(evidence):
    lab4 = work_folder(evidence) / "lab4"
    report = read_json(lab4, "quality-report.json")
    assert report["read"] == {"cases": 40, "documents": 25}
    assert report["accepted"]["cases"] + report["rejected"]["total"] + len(report["duplicates"]) == 40
    assert all(item["reasons"] for item in report["rejected"]["records"])
    manifest = read_json(lab4, "manifest.json")
    documents = [row for row in manifest if row["kind"] == "document"]
    assert len(documents) == report["accepted"]["documents"]
    for row in documents:
        data = (config.LABS_DIR / row["source"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"], f"{row['id']} does not match its source"


def test_evidence_second_run_wrote_nothing(evidence):
    runs = read_json(evidence, "day4-ingestion.json")
    assert any(count["written"] for count in runs["first_run"].values())
    assert all(count["written"] == 0 for count in runs["second_run"].values())
