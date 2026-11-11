"""Offline tests for the Support Assistant v1 application code.

Each section covers one exercise of Week 1. The suite runs without AWS credentials.
Scripted responses and botocore's Stubber replace model calls; in-memory stores
replace AWS storage. These tests check the application's handling of the
supplied responses. Live model behaviour is tested separately.
"""

from __future__ import annotations

import json

import pytest
from botocore.exceptions import ReadTimeoutError
from botocore.stub import Stubber

from support_assistant import config, ingest, retrieval
from support_assistant.assistant import ANSWER_PROMPT, NO_EVIDENCE_TEXT, SupportAssistant
from support_assistant.bedrock import (
    BedrockCallError,
    BedrockClient,
    backoff_delay,
    make_runtime_client,
    native_output_config,
    request_structured,
    should_interrupt,
    should_retry,
    stream_outcome,
    validate_structured,
)
from support_assistant.ledger import EvidenceFolder, Ledger, RunLog, load_prices, model_cost, screen
from support_assistant.loop import SYSTEM_PROMPT, check_limits, run_loop
from support_assistant.prompts import PromptTemplate
from support_assistant.retrieval import (
    KeywordBaseline,
    check_citations,
    compare_retrievers,
    hit_at,
    match_citations,
    passage_from_result,
)
from support_assistant.schemas import CaseSummary
from support_assistant.tools import (
    TOOL_SPECS,
    CallerScope,
    Dispatcher,
    DraftStore,
    LocalCaseStore,
    approve_draft,
    load_users,
    tool_config,
)
from tests.fakes import (
    FakeDynamo,
    FakeRetriever,
    FakeS3,
    ScriptedModel,
    ScriptedRuntime,
    StreamingRuntime,
    client_error,
    converse_response,
    json_lines,
    passage,
    stream_events,
    text_message,
    tool_use_message,
)

FAKE_ACCOUNT = "4" * 12  # built at run time, so no account-shaped number sits in the source


# ------------------------------------------------------------------- Exercise 1


def test_region_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    assert config.region() == "eu-west-2"
    monkeypatch.delenv("AWS_DEFAULT_REGION")
    with pytest.raises(config.ConfigurationError, match="AWS_DEFAULT_REGION"):
        config.region()


def test_owner_initials_are_checked(monkeypatch):
    monkeypatch.setenv("FDE_OWNER", "Ada Lovelace")
    with pytest.raises(config.ConfigurationError):
        config.owner()
    monkeypatch.setenv("FDE_OWNER", "al")
    assert config.tags(1) == {"course": "fde-aws", "lab": "1", "owner": "al"}


def test_describe_identity_reads_a_user_and_an_assumed_role():
    user = config.describe_identity(f"arn:aws:iam::{FAKE_ACCOUNT}:user/fde-learner")
    assert (user.principal_kind, user.principal_name, user.account) == ("user", "fde-learner", "<account-id>")
    role = config.describe_identity(f"arn:aws:sts::{FAKE_ACCOUNT}:assumed-role/FdeLearner/ada")
    assert (role.service, role.principal_kind, role.principal_name, role.session_name) == (
        "sts", "assumed-role", "FdeLearner", "ada")
    assert FAKE_ACCOUNT not in json.dumps(role.as_record())


def test_redact_removes_account_numbers_and_key_identifiers():
    key = "AKIA" + "Q" * 16
    text = config.redact(f"account {FAKE_ACCOUNT} key {key}")
    assert FAKE_ACCOUNT not in text and key not in text
    assert screen(f"{FAKE_ACCOUNT}") == ["account number"]


def test_aws_cli_output_is_redacted(monkeypatch):
    class Completed:
        returncode = 254
        stdout = ""
        stderr = (f"An error occurred (AccessDeniedException) when calling the ListGuardrails operation: "
                  f"User: arn:aws:iam::{FAKE_ACCOUNT}:user/fde-learner is not authorized")

    monkeypatch.setattr(config.shutil, "which", lambda name: "/usr/bin/aws")
    monkeypatch.setattr(config.subprocess, "run", lambda *a, **k: Completed())
    result = config.aws_cli(["bedrock", "list-guardrails", "--region", "eu-west-1"])
    assert result.error_code == "AccessDeniedException"
    assert FAKE_ACCOUNT not in result.stderr and "<account-id>" in result.stderr


# ------------------------------------------------------------------- Exercise 2


def test_one_successful_call_writes_one_priced_row():
    runtime = make_runtime_client()
    ledger = Ledger()
    with Stubber(runtime) as stub:
        stub.add_response("converse", converse_response("Kestrel sells four plans."))
        result = BedrockClient(ledger=ledger, client=runtime).converse(
            [{"role": "user", "content": [{"text": "What does Kestrel sell?"}]}])
    assert result.text() == "Kestrel sells four plans."
    (row,) = ledger.rows()
    assert row["status"] == "succeeded" and row["request_id"] == "req-1" and row["model_id"] == config.MODEL_ID
    price = load_prices().model(config.MODEL_ID)
    assert row["cost_usd"] == pytest.approx((20 * price["input"] + 5 * price["output"]) / 1_000_000)


def test_the_course_model_has_a_price():
    assert load_prices().model(config.MODEL_ID) is not None
    assert load_prices().model(config.COMPARISON_MODEL_ID) is not None


def test_sdk_retries_are_off():
    runtime = make_runtime_client()
    assert runtime.meta.config.retries["total_max_attempts"] == 1


def test_throttle_is_retried_and_every_attempt_is_recorded():
    runtime = make_runtime_client()
    ledger = Ledger()
    waits = []
    with Stubber(runtime) as stub:
        stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
        stub.add_response("converse", converse_response())
        BedrockClient(ledger=ledger, client=runtime, sleep=waits.append, rng=lambda: 0.5).converse(
            [{"role": "user", "content": [{"text": "Hello"}]}])
    first, second = ledger.rows()
    assert (first["status"], first["error_code"], first["will_retry"], first["attempt"]) == (
        "failed", "ThrottlingException", True, 1)
    assert first["cost_usd"] is None and first["cost_status"] == "unknown_usage"
    assert (second["status"], second["attempt"]) == ("succeeded", 2)
    assert waits == [0.5 * config.BACKOFF_BASE_SECONDS]


@pytest.mark.parametrize("code,status", [("AccessDeniedException", 403), ("ValidationException", 400),
                                         ("ResourceNotFoundException", 404)])
def test_errors_a_retry_cannot_fix_are_not_retried(code, status):
    runtime = make_runtime_client()
    ledger = Ledger()
    with Stubber(runtime) as stub:
        stub.add_client_error("converse", service_error_code=code, http_status_code=status)
        with pytest.raises(BedrockCallError) as raised:
            BedrockClient(ledger=ledger, client=runtime, sleep=lambda s: None).converse(
                [{"role": "user", "content": [{"text": "Hello"}]}])
    assert raised.value.code == code and raised.value.attempts == 1
    (row,) = ledger.rows()
    assert row["will_retry"] is False and row["http_status"] == status


def test_retries_stop_at_the_limit():
    errors = [client_error("ThrottlingException", 429) for _ in range(config.MAX_ATTEMPTS)]
    ledger = Ledger()
    client = BedrockClient(ledger=ledger, client=ScriptedRuntime(errors), sleep=lambda s: None)
    with pytest.raises(BedrockCallError) as raised:
        client.converse([{"role": "user", "content": [{"text": "Hello"}]}])
    assert raised.value.attempts == config.MAX_ATTEMPTS
    assert [row["will_retry"] for row in ledger.rows()] == [True] * (config.MAX_ATTEMPTS - 1) + [False]


def test_a_timeout_is_recorded_and_not_retried():
    error = ReadTimeoutError(endpoint_url="https://bedrock-runtime.example")
    ledger = Ledger()
    runtime = ScriptedRuntime([error, converse_response()])
    with pytest.raises(BedrockCallError) as raised:
        BedrockClient(ledger=ledger, client=runtime, sleep=lambda s: None).converse(
            [{"role": "user", "content": [{"text": "Hello"}]}])
    assert raised.value.retryable is False and len(runtime.requests) == 1
    (row,) = ledger.rows()
    assert row["status"] == "timed_out" and row["cost_usd"] is None and row["usage_known"] is False


def test_retry_decision_and_backoff():
    assert should_retry("ThrottlingException") and should_retry("ServiceUnavailableException")
    assert not should_retry("AccessDeniedException") and not should_retry("ReadTimeoutError")
    assert backoff_delay(1, rng=lambda: 1.0) == config.BACKOFF_BASE_SECONDS
    assert backoff_delay(10, rng=lambda: 1.0) == config.BACKOFF_CAP_SECONDS
    assert backoff_delay(3, rng=lambda: 0.0) == 0.0


def test_an_answer_cut_off_at_max_tokens_is_rejected():
    ledger = Ledger()
    client = BedrockClient(ledger=ledger, client=ScriptedRuntime([converse_response('{"case_id": "ca',
                                                                                    stop_reason="max_tokens")]))
    with pytest.raises(BedrockCallError, match="incomplete"):
        client.converse([{"role": "user", "content": [{"text": "Summarise"}]}])
    (row,) = ledger.rows()
    assert row["status"] == "rejected" and row["stop_reason"] == "max_tokens" and row["cost_usd"] is not None


def test_tool_use_and_stop_sequence_count_as_complete():
    for stop in ("tool_use", "stop_sequence"):
        client = BedrockClient(ledger=Ledger(), client=ScriptedRuntime([converse_response(stop_reason=stop)]))
        assert client.converse([{"role": "user", "content": [{"text": "x"}]}]).complete


GOOD_SUMMARY = {"case_id": "case_1001", "category": "billing", "urgency": "low",
                "customer_impact": "The customer paid a small charge they did not expect.",
                "next_step": "Explain the paper bill charge and offer online bills."}


def test_a_valid_structured_answer_becomes_a_record():
    client = BedrockClient(ledger=Ledger(), client=ScriptedRuntime([converse_response(
        "```json\n" + json.dumps(GOOD_SUMMARY) + "\n```")]))
    outcome = request_structured(client, "Summarise case_1001", CaseSummary)
    assert outcome.record == CaseSummary(**GOOD_SUMMARY) and outcome.rejected_reason is None


def test_an_invalid_structured_answer_is_recorded_and_not_used():
    ledger = Ledger()
    bad = dict(GOOD_SUMMARY, urgency="critical")
    client = BedrockClient(ledger=ledger, client=ScriptedRuntime([converse_response(json.dumps(bad))]))
    outcome = request_structured(client, "Summarise case_1001", CaseSummary)
    assert outcome.record is None and "urgency" in outcome.rejected_reason
    assert ledger.rows()[0]["status"] == "rejected"


def test_validation_checks_lengths_in_python():
    record, reason = validate_structured(json.dumps(dict(GOOD_SUMMARY, next_step="Call.")), CaseSummary)
    assert record is None and "next_step" in reason


def test_native_schema_has_no_length_or_pattern_constraints():
    schema = json.loads(native_output_config(CaseSummary, "CaseSummary")["textFormat"]["structure"]["jsonSchema"]["schema"])
    text = json.dumps(schema)
    assert "minLength" not in text and "maxLength" not in text and "pattern" not in text
    assert schema["additionalProperties"] is False


def test_native_structured_output_uses_the_longer_read_timeout(monkeypatch):
    seen = []

    def fake_client(*, read_timeout=None, connect_timeout=None):
        seen.append(read_timeout)
        return ScriptedRuntime([converse_response(json.dumps(GOOD_SUMMARY))])

    monkeypatch.setattr("support_assistant.bedrock.make_runtime_client", fake_client)
    client = BedrockClient(ledger=Ledger())
    request_structured(client, "Summarise case_1001", CaseSummary, native=True)
    assert seen == [config.READ_TIMEOUT_SECONDS, config.STRUCTURED_OUTPUT_READ_TIMEOUT_SECONDS]


def test_an_interrupted_stream_records_unknown_usage():
    ledger = Ledger()
    runtime = StreamingRuntime(stream_events(["one ", "two ", "three ", "four "], complete=True))
    result = BedrockClient(ledger=ledger, client=runtime).stream(
        [{"role": "user", "content": [{"text": "Explain"}]}], max_chunks=2)
    assert result.text == "one two " and not result.complete and runtime.stream.closed
    (row,) = ledger.rows()
    assert row["status"] == "interrupted" and row["usage_known"] is False and row["cost_usd"] is None


def test_a_complete_stream_records_its_usage():
    ledger = Ledger()
    result = BedrockClient(ledger=ledger, client=StreamingRuntime(stream_events(["Hello ", "there."]))).stream(
        [{"role": "user", "content": [{"text": "Hi"}]}])
    assert result.complete and result.usage["outputTokens"] == 40
    assert ledger.rows()[0]["status"] == "succeeded" and ledger.rows()[0]["cost_usd"] > 0


def test_stream_helpers():
    assert should_interrupt(3, 0.1, max_chunks=3, deadline_seconds=None)
    assert should_interrupt(1, 5.0, max_chunks=None, deadline_seconds=2.0)
    assert should_interrupt(1, 0.1, max_chunks=3, deadline_seconds=2.0) is None
    assert stream_outcome("deadline", None, None)[:2] == ("interrupted", None)
    assert stream_outcome(None, "end_turn", {"outputTokens": 1})[0] == "succeeded"
    assert stream_outcome(None, "max_tokens", {"outputTokens": 1})[0] == "rejected"


def test_cost_is_unknown_without_usage_or_price():
    prices = load_prices()
    assert model_cost(prices, config.MODEL_ID, None) == (None, "unknown_usage")
    assert model_cost(prices, "eu.example.unpriced-model", {"inputTokens": 1}) == (None, "no_price")


# ------------------------------------------------------------------- Exercise 3


def dispatcher(scope=None, **kwargs):
    return Dispatcher(case_store=LocalCaseStore(), scope=scope or CallerScope.for_case("case_1001"),
                      run_id="run-test", **kwargs)


def test_the_two_tool_definitions():
    assert set(TOOL_SPECS) == {"lookup_case", "draft_reply"}
    for spec in TOOL_SPECS.values():
        body = spec["toolSpec"]
        assert body["description"] and body["inputSchema"]["json"]["additionalProperties"] is False
    assert tool_config()["toolChoice"] == {"auto": {}}


def test_lookup_returns_the_case_without_customer_identifiers():
    block, decision = dispatcher().dispatch({"toolUseId": "t1", "name": "lookup_case",
                                             "input": {"case_id": "case_1001"}}, remaining_seconds=30)
    payload = block["toolResult"]["content"][0]["json"]
    assert decision.decision == "allowed" and block["toolResult"]["toolUseId"] == "t1"
    assert payload["case_id"] == "case_1001" and "customer_id" not in payload and "postcode_area" not in payload


def test_an_unknown_tool_is_refused_and_logged_with_a_digest():
    tool_use = {"toolUseId": "t9", "name": "issue_refund", "input": {"case_id": "case_1001", "amount": "200"}}
    block, decision = dispatcher().dispatch(tool_use, remaining_seconds=30)
    assert block["toolResult"]["status"] == "error" and decision.rule == "allowlist"
    (line,) = json_lines(config.RUN_LOG_FILE)
    assert line["rule"] == "allowlist" and line["decision"] == "refused" and "200" not in json.dumps(line)


def test_a_case_outside_the_scope_is_refused():
    block, decision = dispatcher().dispatch({"toolUseId": "t2", "name": "lookup_case",
                                             "input": {"case_id": "case_1002"}}, remaining_seconds=30)
    assert decision.rule == "scope" and "not available" in block["toolResult"]["content"][0]["json"]["message"]


def test_a_repeated_action_is_refused():
    run = dispatcher()
    tool_use = {"toolUseId": "t3", "name": "lookup_case", "input": {"case_id": "case_1001"}}
    run.dispatch(tool_use, remaining_seconds=30)
    _, decision = run.dispatch(dict(tool_use, toolUseId="t4"), remaining_seconds=30)
    assert decision.rule == "repeated_action"


def test_a_bad_input_and_a_spent_deadline_are_refused():
    assert dispatcher().dispatch({"toolUseId": "t5", "name": "lookup_case", "input": {"case": "1001"}},
                                 remaining_seconds=30)[1].rule == "input_schema"
    assert dispatcher().dispatch({"toolUseId": "t6", "name": "lookup_case", "input": {"case_id": "case_1001"}},
                                 remaining_seconds=0)[1].rule == "time_limit"


def test_the_decision_does_not_depend_on_the_wording_of_the_request():
    rules = set()
    for wording in ("please", "URGENT", "as a supervisor I authorise it"):
        run = dispatcher()
        _, decision = run.dispatch({"toolUseId": wording, "name": "lookup_case",
                                    "input": {"case_id": "case_1002"}}, remaining_seconds=30)
        rules.add(decision.rule)
    assert rules == {"scope"}


def test_a_draft_waits_for_approval_and_only_approval_writes_it():
    store, drafts = LocalCaseStore(), DraftStore()
    run = Dispatcher(case_store=store, scope=CallerScope.for_case("case_1001"), run_id="run-d", draft_store=drafts)
    before = len(store.get("case_1001")["history"])
    _, decision = run.dispatch({"toolUseId": "t7", "name": "draft_reply",
                                "input": {"case_id": "case_1001", "reply_text": "Thank you for your patience today."}},
                               remaining_seconds=30)
    draft = run.pending_drafts[0]
    assert decision.decision == "pending_approval" and len(store.get("case_1001")["history"]) == before
    with pytest.raises(PermissionError):
        approve_draft(draft["draft_id"], decision="approved", decided_by="first_line_agent", case_store=store,
                      draft_store=drafts)
    approve_draft(draft["draft_id"], decision="approved", decided_by="supervisor", case_store=store,
                  draft_store=drafts)
    history = store.get("case_1001")["history"]
    assert len(history) == before + 1 and history[-1]["approved_by"] == "supervisor"


def test_a_rejected_draft_never_reaches_the_case():
    store, drafts = LocalCaseStore(), DraftStore()
    draft = drafts.create(case_id="case_1001", reply_text="A proposed reply to the customer.", run_id="r")
    approve_draft(draft["draft_id"], decision="rejected", decided_by="supervisor", case_store=store, draft_store=drafts)
    assert all(note.get("author") != "assistant_draft" for note in store.get("case_1001")["history"])


def test_the_loop_runs_a_tool_and_answers():
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1001"}), text_message("It is closed.")],
                          ["tool_use", "end_turn"])
    result = run_loop(model, "What is the status of case_1001?", CallerScope.for_case("case_1001"),
                      case_store=LocalCaseStore())
    assert result.status == "answered" and result.model_calls == 2
    assert result.tool_uses()[0]["name"] == "lookup_case"
    assert result.tool_results()[0]["toolUseId"] == result.tool_uses()[0]["toolUseId"]


def test_the_iteration_limit_counts_model_calls():
    calls = [tool_use_message("lookup_case", {"case_id": "case_1001"}, f"t{i}") for i in range(5)]
    model = ScriptedModel(calls, ["tool_use"] * 5)
    result = run_loop(model, "Look again", CallerScope.for_case("case_1001"), case_store=LocalCaseStore(),
                      max_model_calls=2)
    assert result.status == "stopped_iteration_limit" and model.calls == 2


def test_the_time_limit_is_checked_before_each_call():
    ticks = iter([0.0, 0.0, 100.0, 100.0])
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1001"})], ["tool_use"])
    result = run_loop(model, "Look", CallerScope.for_case("case_1001"), case_store=LocalCaseStore(),
                      deadline_seconds=10, clock=lambda: next(ticks))
    assert result.status == "stopped_time_limit" and model.calls == 1


def test_a_draft_ends_the_run_awaiting_approval():
    model = ScriptedModel([tool_use_message("draft_reply", {"case_id": "case_1001",
                                                            "reply_text": "Here is the reply we propose."})],
                          ["tool_use"])
    result = run_loop(model, "Draft a reply", CallerScope.for_case("case_1001"), case_store=LocalCaseStore())
    assert result.status == "awaiting_approval" and result.pending_drafts


def test_check_limits():
    assert check_limits(6, 6, 0, 10)[0] == "iteration_limit"
    assert check_limits(1, 6, 11, 10)[0] == "time_limit"
    assert check_limits(1, 6, 1, 10) is None


# ----------------------------------------------- Exercises 4 and 5, part one


def dataset_plan():
    return ingest.plan_ingestion(*ingest.dataset_sources(), config.reference_date())


def test_the_dataset_plan_matches_the_contract():
    plan = dataset_plan()
    report = ingest.quality_report(plan)
    assert report["read"] == {"cases": 40, "documents": 25}
    assert report["accepted"]["cases"] + report["rejected"]["total"] + len(report["duplicates"]) == 40
    assert all(rejected.reasons for rejected in plan.rejected)
    assert report["accepted"]["documents"] == 25


def test_every_kind_of_fixture_is_rejected_for_its_rule():
    report = ingest.quality_report(ingest.plan_ingestion(*ingest.fixture_sources(), config.reference_date()))
    assert report["accepted"]["cases"] == 1
    assert {"summary", "plan", "opened_at", "priority", "case_id", "file type", "audience",
            "last_reviewed"} <= set(report["rejected"]["by_rule"])
    assert [d["identical"] for d in report["duplicates"]] == [True, False]


def test_validate_case_lists_every_broken_rule():
    record = json.loads((config.DATA_DIR / "cases.json").read_text(encoding="utf-8"))["cases"][0]
    assert ingest.validate_case(record) == []
    broken = dict(record, plan="fibre_2000", opened_at="yesterday")
    broken.pop("summary")
    reasons = ingest.validate_case(broken)
    assert {reason.split(":")[0] for reason in reasons} == {"plan", "opened_at", "summary"}


def test_a_second_ingestion_run_writes_nothing():
    plan = dataset_plan()
    s3, dynamodb = FakeS3(), FakeDynamo()
    manifest, first = ingest.ingest(plan, s3=s3, dynamodb=dynamodb, bucket="b", table="t")
    assert first["table"]["written"] == len(plan.cases) and first["curated"]["written"] > 0
    again, second = ingest.ingest(plan, s3=s3, dynamodb=dynamodb, bucket="b", table="t")
    assert all(counts["written"] == 0 for counts in second.values())
    assert again == manifest


def test_the_manifest_traces_each_document_to_its_source():
    manifest, _ = ingest.ingest(dataset_plan(), s3=FakeS3(), dynamodb=FakeDynamo(), bucket="b", table="t")
    documents = [row for row in manifest if row["kind"] == "document"]
    assert len(documents) == 25
    row = documents[0]
    source = config.LABS_DIR / row["source"]
    assert ingest.sha256_bytes(source.read_bytes()) == row["sha256"]
    assert row["location"].startswith("s3://b/curated/documents/") and row["contract_version"] == "1.0"


def test_metadata_files_use_the_typed_format_under_their_prefix():
    s3 = FakeS3()
    ingest.ingest(dataset_plan(), s3=s3, dynamodb=FakeDynamo(), bucket="b", table="t")
    key = "curated/metadata/curated/documents/kd-07-refund-rules.md.metadata.json"
    sidecar = json.loads(s3.objects[key]["Body"])
    assert sidecar["metadataAttributes"]["audience"] == {"value": {"type": "STRING", "stringValue": "customer"}}
    assert sidecar["metadataAttributes"]["last_reviewed"]["value"]["type"] == "NUMBER"


def test_a_bounded_wait_gives_up():
    now = iter(range(0, 1000, 5))
    with pytest.raises(ingest.WaitTimeout, match="did not finish"):
        ingest.wait_for(lambda: (False, "SYNCING"), timeout=20, interval=5, what="sync",
                        sleep=lambda s: None, clock=lambda: next(now))


def test_the_keyword_baseline_is_deterministic():
    baseline = KeywordBaseline(retrieval.load_corpus())
    first = baseline.rank("What does a solid red light on my KR-3 router mean?")
    assert first == baseline.rank("What does a solid red light on my KR-3 router mean?")
    assert first[0][0] == "kd_08"


def test_hit_at():
    assert hit_at({"kd_02"}, ["kd_05", "kd_02"], 5) is True
    assert hit_at({"kd_02"}, ["kd_05", "kd_02"], 1) is False
    assert hit_at(set(), ["kd_05"], 5) is None


def test_the_comparison_measures_both_retrievers_the_same_way():
    questions = [{"question_id": "q1", "question": "router red light", "supporting_documents": ["kd_08"]},
                 {"question_id": "q2", "question": "student discount", "supporting_documents": []}]
    report = compare_retrievers(questions, KeywordBaseline(retrieval.load_corpus()),
                                FakeRetriever([passage("kd_08", 0.9)]))
    assert report["answerable_questions"] == 1 and report["knowledge_base"]["hit_rate_top_k"] == 1.0
    assert report["no_evidence_top_scores"] == {"q2": 0.9}


def test_a_retrieve_result_becomes_a_passage():
    result = {"content": {"text": "Refunds take five days."}, "score": 0.81,
              "location": {"type": "S3", "s3Location": {"uri": "https://b.s3.example/curated/documents/kd-07-refund-rules.md"}},
              "metadata": {"doc_id": "kd_07", "audience": "customer", "status": "current"}}
    item = passage_from_result(result, 1)
    assert (item.doc_id, item.score, item.rank) == ("kd_07", 0.81, 1)
    del result["metadata"]["doc_id"]
    assert passage_from_result(result, 1).doc_id == "kd_07"


# -------------------------------------------------- Support Assistant v1


USERS = None


def users():
    global USERS
    USERS = USERS or load_users()
    return USERS


def test_customer_scope_reads_only_own_cases():
    scope = CallerScope.for_user(users()["user_customer_01"])
    store = LocalCaseStore()
    own = [case for case in store.case_ids() if scope.allows_case(store.get(case))]
    assert own and all(store.get(case)["customer_id"] == users()["user_customer_01"]["customer_id"] for case in own)


def test_the_citation_check():
    manifest = {"kd_01": {"status": "current"}}
    supplied = [passage("kd_01", 0.8)]
    citations, problems = check_citations("Call us any day [kd_01].", supplied, manifest)
    assert [c.doc_id for c in citations] == ["kd_01"] and problems == []
    assert check_citations("No citation here.", supplied, manifest)[1] == ["the answer cites no document"]
    assert any("not among" in p for p in check_citations("See [kd_99].", supplied, manifest)[1])
    assert check_citations("See [kd_24].", [passage("kd_24", 0.9)], manifest)[1] == \
        ["kd_24 is not in the dataset manifest"]
    assert match_citations("See [kd_99].", supplied)[1] == ["kd_99 was not among the passages supplied"]


def assistant_with(passages, model, prompt=None):
    return SupportAssistant(client=model, retriever=FakeRetriever(passages), case_store=LocalCaseStore(),
                            manifest={"kd_01": {"status": "current"}, "kd_02": {"status": "current"}},
                            prompt=prompt)


def test_a_document_question_is_answered_from_the_passages_without_a_filter():
    model = ScriptedModel([text_message("Contact us by chat [kd_01].")], ["end_turn"])
    assistant = assistant_with([passage("kd_01", 0.8)], model)
    response = assistant.ask("How do I contact you?", users()["user_customer_01"], run_id="r-doc")
    assert response.kind == "answer" and response.citations[0].doc_id == "kd_01" and response.run_id == "r-doc"
    assert assistant.retriever.filters == [None], "Week 2 adds the caller's document filter"
    assert model.systems == [None] and model.seen[0][0]["content"][0]["text"].startswith(ANSWER_PROMPT)


def test_an_answer_with_a_bad_citation_is_refused():
    model = ScriptedModel([text_message("Contact us by chat [kd_09].")], ["end_turn"])
    response = assistant_with([passage("kd_01", 0.8)], model).ask("How do I contact you?",
                                                                  users()["user_customer_01"])
    assert response.kind == "refused" and "kd_09" in response.reason


def test_a_case_question_goes_through_the_loop_with_the_passages_as_context():
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1003"}), text_message("It is open.")],
                          ["tool_use", "end_turn"])
    response = assistant_with([passage("kd_06", 0.7)], model).ask("Why was my bill high on case_1003?",
                                                                  users()["user_customer_01"])
    assert response.kind == "answer" and response.tools_used == ["lookup_case"] and response.model_calls == 2
    assert model.systems == [SYSTEM_PROMPT, SYSTEM_PROMPT]
    assert "Kestrel policy passages that may help" in model.seen[0][0]["content"][0]["text"]


def test_a_prompt_version_reaches_both_routes():
    version = PromptTemplate(system="SYSTEM PART", message="MESSAGE PART {{passages}} {{question}}", version="7")
    document = ScriptedModel([text_message("By chat [kd_01].")], ["end_turn"])
    assistant_with([passage("kd_01", 0.8)], document, version).ask("How do I contact you?",
                                                                   users()["user_customer_01"])
    assert document.systems == ["SYSTEM PART"]
    assert document.seen[0][0]["content"][0]["text"].startswith("MESSAGE PART <passage doc_id=\"kd_01\"")
    case = ScriptedModel([text_message("I can't read that case.")], ["end_turn"])
    assistant_with([passage("kd_01", 0.8)], case, version).ask("Status of case_1016?", users()["user_customer_01"])
    assert case.systems == ["SYSTEM PART"]


def test_a_no_evidence_reply_with_extras_is_still_no_evidence():
    model = ScriptedModel([text_message("NO_EVIDENCE [kd_01]")], ["end_turn"])
    response = assistant_with([passage("kd_01", 0.8)], model).ask("Do you sell TV?", users()["user_customer_01"])
    assert response.kind == "no_evidence" and response.text == NO_EVIDENCE_TEXT and response.model_calls == 1


def test_evidence_records_are_redacted_and_frozen():
    folder = EvidenceFolder()
    folder.write("day1-identity.json", {"arn": f"arn:aws:iam::{FAKE_ACCOUNT}:user/fde-learner"})
    assert FAKE_ACCOUNT not in (folder.root / "day1-identity.json").read_text()
    frozen = folder.freeze()
    assert "day1-identity.json" in frozen["files"] and frozen["secret_findings"] == {}


def test_teardown_needs_confirmation():
    from support_assistant.__main__ import main

    with pytest.raises(SystemExit):
        main(["teardown"])


def test_the_run_log_never_holds_the_raw_input():
    line = RunLog().decision(run_id="r", rule="scope", decision="refused", reason="outside scope", tool="lookup_case",
                             input_value={"case_id": "case_1002", "note": "private words"})
    assert "private words" not in json.dumps(line) and len(line["input_digest"]) == 16


def test_identifiers_and_digests_are_not_mistaken_for_account_numbers():
    request_id = "cad76692-b80b-419d-83ef-" + "7" * 12
    assert config.redact(f'"request_id": "{request_id}"') == f'"request_id": "{request_id}"'
    assert config.redact("digest " + "a" + "1" * 12 + "b") == "digest " + "a" + "1" * 12 + "b"
    assert config.redact(f'"Account": "{FAKE_ACCOUNT}"') == '"Account": "<account-id>"'
    from support_assistant.ledger import new_id

    assert all(new_id()[0].isalpha() for _ in range(50))


def test_knowledge_base_calls_are_priced_from_the_register():
    ledger = Ledger()
    retrieve = ledger.record(operation="retrieve", status="succeeded")
    agentic = ledger.record(operation="agentic_retrieve", status="succeeded")
    prices = load_prices()
    assert retrieve["cost_status"] == "calculated" and retrieve["cost_usd"] == prices.retrieve_per_1000 / 1000
    assert agentic["cost_status"] == "partial" and agentic["cost_usd"] == prices.agentic_per_1000 / 1000
