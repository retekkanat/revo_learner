"""Exercise 3 check: tool definitions, dispatch, limits and approval.

Run from the lab folder:  uv run --directory starter/exercise-3 python -m pytest ../checks/check_exercise_3.py
The scripted model here tests your loop's own code. It is never evidence of what
a model does.
"""

from __future__ import annotations

import json

import pytest
from kestrel_doubles import ScriptedModel, text_message, tool_use_message
from kestrel_evidence import read_json, read_lines, work_folder

from support_assistant import config
from support_assistant.loop import check_limits, run_loop
from support_assistant.tools import CallerScope, Dispatcher, DraftStore, LocalCaseStore, TOOL_SPECS, approve_draft, \
    tool_config


def dispatcher(case_id="case_1001", **kwargs):
    return Dispatcher(case_store=LocalCaseStore(), scope=CallerScope.for_case(case_id), run_id="check", **kwargs)


def test_the_draft_reply_definition():
    spec = TOOL_SPECS["draft_reply"]["toolSpec"]
    schema = spec["inputSchema"]["json"]
    assert spec["name"] == "draft_reply" and len(spec["description"]) > 40
    assert set(schema["required"]) == {"case_id", "reply_text"} and schema["additionalProperties"] is False
    assert [tool["toolSpec"]["name"] for tool in tool_config()["tools"]] == ["lookup_case", "draft_reply"]


def test_lookup_runs_in_scope_and_returns_no_customer_identifiers():
    block, decision = dispatcher().dispatch({"toolUseId": "a", "name": "lookup_case",
                                             "input": {"case_id": "case_1001"}}, remaining_seconds=10)
    assert decision.decision == "allowed" and block["toolResult"]["toolUseId"] == "a"
    assert "customer_id" not in block["toolResult"]["content"][0]["json"]


@pytest.mark.parametrize("tool_use,rule", [
    ({"toolUseId": "b", "name": "issue_refund", "input": {"case_id": "case_1001"}}, "allowlist"),
    ({"toolUseId": "c", "name": "lookup_case", "input": {"case_id": "case_1002"}}, "scope"),
    ({"toolUseId": "d", "name": "lookup_case", "input": {"id": "case_1001"}}, "input_schema"),
])
def test_requests_are_refused_by_rule(tool_use, rule):
    block, decision = dispatcher().dispatch(tool_use, remaining_seconds=10)
    assert decision.rule == rule and decision.decision == "refused"
    assert block["toolResult"]["status"] == "error"


def test_a_repeated_request_is_refused():
    run = dispatcher()
    run.dispatch({"toolUseId": "e", "name": "lookup_case", "input": {"case_id": "case_1001"}}, remaining_seconds=10)
    assert run.dispatch({"toolUseId": "f", "name": "lookup_case", "input": {"case_id": "case_1001"}},
                        remaining_seconds=10)[1].rule == "repeated_action"


def test_refusal_lines_hold_a_digest_and_not_the_input():
    dispatcher().dispatch({"toolUseId": "g", "name": "issue_refund",
                           "input": {"case_id": "case_1001", "note": "secret words"}}, remaining_seconds=10)
    text = config.RUN_LOG_FILE.read_text(encoding="utf-8")
    assert "secret words" not in text and '"input_digest"' in text


def test_a_draft_is_only_a_proposal_until_a_supervisor_approves():
    store, drafts = LocalCaseStore(), DraftStore()
    run = Dispatcher(case_store=store, scope=CallerScope.for_case("case_1001"), run_id="check", draft_store=drafts)
    before = len(store.get("case_1001")["history"])
    _, decision = run.dispatch({"toolUseId": "h", "name": "draft_reply",
                                "input": {"case_id": "case_1001", "reply_text": "Thank you, we have fixed it."}},
                               remaining_seconds=10)
    assert decision.decision == "pending_approval" and len(store.get("case_1001")["history"]) == before
    draft_id = run.pending_drafts[0]["draft_id"]
    with pytest.raises(PermissionError):
        approve_draft(draft_id, decision="approved", decided_by="customer", case_store=store, draft_store=drafts)
    approve_draft(draft_id, decision="approved", decided_by="supervisor", case_store=store, draft_store=drafts)
    assert len(store.get("case_1001")["history"]) == before + 1


def test_limits_stop_the_loop():
    assert check_limits(3, 3, 0.0, 10.0)[0] == "iteration_limit"
    assert check_limits(0, 3, 10.0, 10.0)[0] == "time_limit"
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1001"}, f"t{i}") for i in range(4)],
                          ["tool_use"] * 4)
    result = run_loop(model, "Keep looking", CallerScope.for_case("case_1001"), case_store=LocalCaseStore(),
                      max_model_calls=2)
    assert result.status == "stopped_iteration_limit" and model.calls == 2


def test_the_loop_answers_after_a_tool_result():
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1001"}), text_message("Closed.")],
                          ["tool_use", "end_turn"])
    result = run_loop(model, "Status of case_1001?", CallerScope.for_case("case_1001"), case_store=LocalCaseStore())
    assert result.status == "answered" and result.tool_results()[0]["status"] == "success"


def test_evidence_refusals_come_from_code(evidence):
    record = read_json(evidence, "day3-refusals.json")
    rules = {item["rule"] for item in record["refusals"]}
    assert {"allowlist", "scope", "repeated_action"} <= rules
    assert record["injected_note_run"]["status"], "record what the loop did on the case with the injected note"
    rephrased = record["rephrasing"]
    assert len(rephrased) >= 2 and len({item["dispatcher_rule"] for item in rephrased}) == 1


def test_evidence_approval_boundary(evidence):
    record = read_json(evidence, "day3-loop.json")
    assert record["draft_run"]["status"] == "awaiting_approval"
    assert record["history_before_approval"] == record["history_after_draft"]
    assert record["history_after_approval"] == record["history_before_approval"] + 1
    lines = read_lines(work_folder(evidence) / "runlog.jsonl")
    assert any(line["rule"] == "approval" and line["decision"] == "approved" for line in lines)
    assert all("reply_text" not in json.dumps(line) for line in lines)
