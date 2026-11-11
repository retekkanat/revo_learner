"""Exercise 2 check: response validation, streaming, retries and the call ledger.

Run from the lab folder:  uv run --directory starter/exercise-2 python -m pytest ../checks/check_exercise_2.py
Injected failures here use botocore's Stubber and scripted responses. They test
your client's own code and are never evidence of what the model does.
"""

from __future__ import annotations

import json

import pytest
from botocore.stub import Stubber
from kestrel_doubles import ScriptedRuntime, StreamingRuntime, client_error, converse_response, stream_events
from kestrel_evidence import read_json, read_lines, work_folder

from support_assistant import config
from support_assistant.bedrock import (
    BedrockCallError,
    BedrockClient,
    backoff_delay,
    make_runtime_client,
    result_from_response,
    should_interrupt,
    should_retry,
    stream_outcome,
    validate_structured,
)
from support_assistant.ledger import Ledger
from support_assistant.schemas import CaseSummary

SUMMARY = {"case_id": "case_1001", "category": "billing", "urgency": "low",
           "customer_impact": "The customer paid a charge they did not expect.",
           "next_step": "Explain the charge and offer online bills."}


def test_result_from_response_reads_every_field():
    result = result_from_response(converse_response("Hello.", request_id="req-42"), elapsed_ms=12, attempts=1,
                                  model_id=config.MODEL_ID)
    assert (result.stop_reason, result.request_id, result.latency_ms) == ("end_turn", "req-42", 321)
    assert result.usage["inputTokens"] == 20 and result.text() == "Hello."


def test_a_first_call_writes_one_ledger_row():
    runtime = make_runtime_client()
    ledger = Ledger()
    with Stubber(runtime) as stub:
        stub.add_response("converse", converse_response())
        BedrockClient(ledger=ledger, client=runtime).converse([{"role": "user", "content": [{"text": "Hi"}]}])
    (row,) = ledger.rows()
    assert row["status"] == "succeeded" and row["request_id"] == "req-1" and row["cost_usd"] is not None


def test_validate_structured_accepts_a_good_answer_and_names_bad_fields():
    record, reason = validate_structured(json.dumps(SUMMARY), CaseSummary)
    assert record is not None and reason is None
    record, reason = validate_structured(json.dumps(dict(SUMMARY, urgency="critical")), CaseSummary)
    assert record is None and "urgency" in reason
    record, reason = validate_structured('{"case_id": "case_10', CaseSummary)
    assert record is None and reason


def test_should_interrupt_and_stream_outcome():
    assert should_interrupt(5, 0.0, max_chunks=5, deadline_seconds=None)
    assert should_interrupt(1, 9.0, max_chunks=None, deadline_seconds=3.0)
    assert should_interrupt(1, 0.0, max_chunks=5, deadline_seconds=3.0) is None
    status, usage, _ = stream_outcome("chunk limit", None, None)
    assert (status, usage) == ("interrupted", None)
    assert stream_outcome(None, "end_turn", {"outputTokens": 3})[0] == "succeeded"


def test_an_interrupted_stream_has_unknown_cost():
    ledger = Ledger()
    runtime = StreamingRuntime(stream_events(["a", "b", "c", "d"]))
    result = BedrockClient(ledger=ledger, client=runtime).stream([{"role": "user", "content": [{"text": "x"}]}],
                                                                 max_chunks=2)
    assert not result.complete and runtime.stream.closed
    assert ledger.rows()[0]["status"] == "interrupted" and ledger.rows()[0]["cost_usd"] is None


def test_retry_rules():
    assert should_retry("ThrottlingException")
    for code in ("AccessDeniedException", "ValidationException", "ResourceNotFoundException", "ReadTimeoutError"):
        assert not should_retry(code)
    assert 0 <= backoff_delay(2, rng=lambda: 0.5) <= config.BACKOFF_CAP_SECONDS
    assert backoff_delay(20, rng=lambda: 1.0) == config.BACKOFF_CAP_SECONDS


def test_a_throttle_is_retried_and_an_access_denial_is_not():
    ledger = Ledger()
    client = BedrockClient(ledger=ledger, client=ScriptedRuntime([client_error("ThrottlingException", 429),
                                                                  converse_response()]), sleep=lambda s: None)
    client.converse([{"role": "user", "content": [{"text": "x"}]}])
    assert [row["status"] for row in ledger.rows()] == ["failed", "succeeded"]
    denied = BedrockClient(ledger=Ledger(), client=ScriptedRuntime([client_error("AccessDeniedException", 403)]),
                           sleep=lambda s: None)
    with pytest.raises(BedrockCallError) as raised:
        denied.converse([{"role": "user", "content": [{"text": "x"}]}])
    assert raised.value.attempts == 1


def test_evidence_ledger_tells_the_whole_story(evidence):
    rows = read_lines(work_folder(evidence) / "calls.jsonl")
    converse = [row for row in rows if row["operation"] in {"converse", "converse_stream"}]
    assert any(row["status"] == "succeeded" and row["request_id"] for row in converse), "no successful call"
    assert any(row["status"] == "rejected" for row in converse), "no rejected answer"
    assert any(row["status"] == "interrupted" and row["cost_usd"] is None for row in converse), "no interrupted stream"
    assert any(row["status"] == "timed_out" and row["cost_usd"] is None for row in converse), "no timeout"
    assert any(row["error_code"] == "AccessDeniedException" and not row["will_retry"] for row in converse)
    assert any(row["error_code"] == "ThrottlingException" and row["will_retry"] for row in converse)
    for row in converse:
        if row["usage_known"]:
            assert row["cost_usd"] is not None or row["cost_status"] == "no_price"


def test_evidence_day2_records(evidence):
    first = read_json(evidence, "day2-first-call.json")
    for key in ("request_id", "stop_reason", "usage", "latency_ms", "model_id"):
        assert first.get(key) is not None, f"the first-call record has no {key}"
    structured = read_json(evidence, "day2-structured.json")
    assert structured["valid_record"] and structured["rejected_reason"]
