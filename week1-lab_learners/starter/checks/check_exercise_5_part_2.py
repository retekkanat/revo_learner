"""Exercise 5, part two, check: the template, the prompt version on both routes, and the regression rule.

Run from the lab folder:
    uv run --directory starter/exercise-5-part-2 python -m pytest ../checks/check_exercise_5_part_2.py
The code checks always run. The record checks run when KESTREL_EVIDENCE names
your records folder, as the workbook's check cell sets it. The scripted model
tests your code's routing; it is never evidence of what a model does.
"""

from __future__ import annotations

import pytest
from kestrel_doubles import FakeRetriever, ScriptedModel, passage, text_message, tool_use_message
from kestrel_evidence import read_json, secrets_in

from support_assistant.assistant import ANSWER_PROMPT, SupportAssistant
from support_assistant.loop import SYSTEM_PROMPT
from support_assistant.prompts import LOCAL_PROMPT, REVISED_PROMPT, PromptTemplate, regression_problems, \
    render_template
from support_assistant.tools import LocalCaseStore, load_users

USERS = load_users()
SUMMARY = {"questions": 30, "injection_cases": 5, "cited_answers": 18, "out_of_scope_requests": 0}


def test_render_fills_each_variable_in_one_pass():
    assert render_template("Q: {{question}}", {"passages": "P", "question": "Why?"}) == "Q: Why?"
    filled = render_template("{{passages}} | {{question}}", {"passages": "a {{question}} b", "question": "Q"})
    assert filled == "a {{question}} b | Q", "a value is inserted as it is and never filled in again"


def test_render_refuses_a_missing_or_an_undeclared_variable():
    with pytest.raises(ValueError):
        render_template("{{question}}", {"question": "Q"})
    with pytest.raises(ValueError):
        render_template("{{questoin}}", {"passages": "P", "question": "Q"})


def test_version_1_is_the_prompt_the_assistant_already_sends():
    system, message = LOCAL_PROMPT.render(passages="PASSAGES", question="QUESTION")
    assert system == SYSTEM_PROMPT
    assert message == f"{ANSWER_PROMPT}\n\nPASSAGES\n\nQuestion: QUESTION"


def test_version_2_keeps_what_the_code_depends_on():
    assert REVISED_PROMPT is not None, "write REVISED_PROMPT in prompts.py"
    assert set(REVISED_PROMPT.variables) == {"passages", "question"}
    _, message = REVISED_PROMPT.render(passages="PASSAGES", question="QUESTION")
    assert "PASSAGES" in message and "QUESTION" in message
    assert "NO_EVIDENCE" in message and "[kd_" in message, "keep the exact reply NO_EVIDENCE and the citation rule"
    assert not REVISED_PROMPT.same_text(LOCAL_PROMPT), "version 2 must differ from version 1"


def assistant(model, prompt):
    return SupportAssistant(client=model, retriever=FakeRetriever([passage("kd_01", 0.9)]),
                            case_store=LocalCaseStore(), manifest={"kd_01": {"status": "current"}}, prompt=prompt)


TEMPLATE = PromptTemplate(system="SYSTEM PART", message="MESSAGE PART {{passages}} {{question}}")


def test_the_document_route_sends_both_parts_of_the_version():
    model = ScriptedModel([text_message("By chat [kd_01].")], ["end_turn"])
    response = assistant(model, TEMPLATE).ask("How do I contact you?", USERS["user_customer_01"])
    assert response.kind == "answer" and [citation.doc_id for citation in response.citations] == ["kd_01"]
    assert model.systems == ["SYSTEM PART"]
    assert model.seen[0][0]["content"][0]["text"].startswith("MESSAGE PART")


def test_the_case_route_sends_the_system_part():
    model = ScriptedModel([tool_use_message("lookup_case", {"case_id": "case_1002"}), text_message("It is closed.")],
                          ["tool_use", "end_turn"])
    response = assistant(model, TEMPLATE).ask("What is the status of case_1002?", USERS["user_agent_01"])
    assert response.tools_used == ["lookup_case"]
    assert model.systems == ["SYSTEM PART", "SYSTEM PART"], "both routes must use the same prompt version"


def test_without_a_version_the_assistant_keeps_the_prompts_in_code():
    model = ScriptedModel([text_message("By chat [kd_01].")], ["end_turn"])
    assistant(model, None).ask("How do I contact you?", USERS["user_customer_01"])
    assert model.systems == [None]
    assert model.seen[0][0]["content"][0]["text"].startswith(ANSWER_PROMPT)


def test_the_regression_rule():
    assert regression_problems(SUMMARY, dict(SUMMARY)) == []
    assert regression_problems(SUMMARY, dict(SUMMARY, cited_answers=19)) == []
    fell = regression_problems(SUMMARY, dict(SUMMARY, cited_answers=17))
    assert len(fell) == 1 and "18" in fell[0] and "17" in fell[0], "name the measure and both values"
    assert regression_problems(SUMMARY, dict(SUMMARY, cited_answers=17), tolerance=1) == []
    assert regression_problems(SUMMARY, dict(SUMMARY, out_of_scope_requests=1))
    assert regression_problems(SUMMARY, dict(SUMMARY, questions=29)), "runs of different sizes are not comparable"


def test_evidence_saved_version_runs(evidence):
    runs = sorted(evidence.glob("day5-prompt-version-*.json"))
    assert len(runs) >= 2, "run version 1 and your version 2 on the question set and the injection cases"
    for path in runs:
        record = read_json(evidence, path.name)
        assert record["summary"]["questions"] == 30 and record["summary"]["injection_cases"] == 5
        for row in record["questions"]:
            if row["kind"] == "answer":
                assert row["request_ids"], f"{path.name}: {row['question_id']} has no request identifier"


def test_evidence_teardown(evidence):
    if not (evidence / "day5-teardown.json").is_file():
        pytest.skip("remove the resources when you finish, as the last cell of the exercise does")
    left = read_json(evidence, "day5-teardown.json")["left"]
    assert not any(left["tagged"].values()), "something still carries your course tags"
    assert not any(left.get(key) for key in ("buckets", "knowledge_bases", "tables", "roles", "prompts")), \
        "a resource of the exercise is left"


def test_evidence_holds_no_account_number_or_key(evidence):
    assert secrets_in(evidence) == []
