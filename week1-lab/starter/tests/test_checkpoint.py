"""Offline tests for the supplied parts of the starter package.

The tests cover configuration, the ledger, evidence files, data schemas, stores,
keyword retrieval, Day 4 citation matching and the command line. They can run
before learners complete any exercise. The exercise acceptance checks in
`checks/` test the functions assigned to learners.
"""

from __future__ import annotations

import json

import pytest

from support_assistant import config, ingest, retrieval
from support_assistant.bedrock import make_runtime_client, parse_json_object
from support_assistant.ledger import EvidenceFolder, Ledger, load_prices, model_cost
from support_assistant.schemas import CaseRecord, CaseSummary, DocumentMetadata, Passage
from support_assistant.tools import LOOKUP_CASE_SPEC, CallerScope, DraftStore, LocalCaseStore, load_users

FAKE_ACCOUNT = "7" * 12


def test_the_dataset_is_present():
    for name in ("cases.json", "users.json", "questions.json", "pricing.json", "kestrel-company.md"):
        assert (config.DATA_DIR / name).is_file()
    assert len(list((config.DATA_DIR / "documents").glob("*.md"))) == 25


def test_region_and_owner_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with pytest.raises(config.ConfigurationError):
        config.region()
    monkeypatch.setenv("FDE_OWNER", "x")
    with pytest.raises(config.ConfigurationError):
        config.owner()


def test_resource_names_are_stable_and_hold_no_account_number():
    first, second = config.resource_names(), config.resource_names()
    assert first == second and first.bucket.startswith("fde-tt-kestrel-")
    assert not any(ch.isdigit() for ch in first.bucket)


def test_redaction():
    assert config.redact(f"arn:aws:iam::{FAKE_ACCOUNT}:user/x") == "arn:aws:iam::<account-id>:user/x"


def test_the_model_is_one_constant_with_a_price():
    assert config.MODEL_ID.startswith("eu.")
    assert load_prices().model(config.MODEL_ID) is not None


def test_ledger_rows_and_unknown_cost():
    ledger = Ledger()
    row = ledger.record(operation="converse", status="succeeded", model_id=config.MODEL_ID,
                        usage={"inputTokens": 100, "outputTokens": 10})
    assert row["cost_usd"] > 0 and row["cost_status"] == "calculated"
    row = ledger.record(operation="converse", status="interrupted", model_id=config.MODEL_ID, usage=None)
    assert row["cost_usd"] is None and row["cost_status"] == "unknown_usage"
    assert ledger.totals()["attempts_with_unknown_cost"] == 1
    assert model_cost(load_prices(), "eu.example.unpriced", {"inputTokens": 1}) == (None, "no_price")


def test_sdk_retries_are_off():
    assert make_runtime_client().meta.config.retries["total_max_attempts"] == 1


def test_parse_json_object_ignores_a_code_fence():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_the_contract_models():
    record = json.loads((config.DATA_DIR / "cases.json").read_text(encoding="utf-8"))["cases"][0]
    assert CaseRecord.model_validate(record).case_id == record["case_id"]
    assert "minLength" not in json.dumps(CaseSummary.model_json_schema())
    meta = DocumentMetadata(doc_id="kd_01", title="T", last_reviewed="2026-01-01", owner_team="billing",
                            audience="customer", status="current")
    assert meta.audience == "customer"


def test_documents_parse_with_their_header():
    path = sorted((config.DATA_DIR / "documents").glob("*.md"))[0]
    parsed, reasons = ingest.parse_document(path, config.reference_date())
    assert reasons == [] and parsed.metadata.doc_id == path.name[:5].replace("-", "_")


def test_the_lookup_tool_definition_is_supplied():
    spec = LOOKUP_CASE_SPEC["toolSpec"]
    assert spec["name"] == "lookup_case" and spec["inputSchema"]["json"]["required"] == ["case_id"]


def test_the_case_store_and_the_draft_store():
    store = LocalCaseStore()
    assert store.get("case_1001")["case_id"] == "case_1001" and store.get("case_0000") is None
    draft = DraftStore().create(case_id="case_1001", reply_text="A proposed reply.", run_id="r")
    assert draft["status"] == "pending_approval"


def test_caller_scope_from_users():
    users = load_users()
    assert CallerScope.for_user(users["user_customer_01"]).audiences == ("customer",)
    assert CallerScope.for_user(users["user_agent_01"]).may_draft


def test_the_keyword_baseline_runs_locally():
    baseline = retrieval.KeywordBaseline(retrieval.load_corpus())
    assert baseline.rank("solid red light router")[0][0] == "kd_08"


def test_the_day_4_citation_match():
    supplied = [Passage(doc_id="kd_01", text="T", score=0.9, rank=1, location="s3://bucket/curated/documents/kd-01.md")]
    citations, problems = retrieval.match_citations("Any day [kd_01]. Every day [kd_01].", supplied)
    assert [(c.doc_id, c.location) for c in citations] == [("kd_01", supplied[0].location)] and problems == []
    assert retrieval.match_citations("No citation.", supplied)[1] == ["the answer cites no document"]
    assert retrieval.match_citations("See [kd_05].", supplied)[1] == ["kd_05 was not among the passages supplied"]


def test_evidence_is_redacted_and_frozen():
    folder = EvidenceFolder()
    folder.write("note.json", {"arn": f"arn:aws:iam::{FAKE_ACCOUNT}:user/x"})
    assert FAKE_ACCOUNT not in (folder.root / "note.json").read_text()
    assert folder.freeze()["secret_findings"] == {}


def test_teardown_asks_for_confirmation():
    from support_assistant.__main__ import main

    with pytest.raises(SystemExit):
        main(["teardown"])
