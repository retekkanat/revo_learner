"""Offline tests for Exercise 5, part two: the template, its versions and the regression rule.

An in-memory stand-in replaces the Prompt Management API, and scripted models
replace Amazon Bedrock. The live run of the exercise is recorded in
`readiness/exercise-5-part-2.md`.
"""

from __future__ import annotations

import pytest

from support_assistant import config
from support_assistant.assistant import ANSWER_PROMPT, course_prompts, format_passages, prompt_is_deleted
from support_assistant.loop import SYSTEM_PROMPT
from support_assistant.prompts import (
    INJECTED_CASE,
    INJECTION_CASES,
    LOCAL_PROMPT,
    REVISED_PROMPT,
    PromptTemplate,
    chat_variant,
    ensure_version,
    find_prompt,
    load_version,
    regression_problems,
    render_template,
    run_injection_cases,
    summarise,
    version_numbers,
)
from support_assistant.tools import LocalCaseStore
from tests.fakes import ScriptedModel, client_error, passage, text_message, tool_use_message


class FakeAgent:
    """Enough of the `bedrock-agent` Prompt Management API, with one prompt summary for each page."""

    def __init__(self) -> None:
        self.prompts: dict[str, dict] = {}
        self.created_versions = 0

    def _summary(self, prompt_id: str, version: str) -> dict:
        return {"name": self.prompts[prompt_id]["name"], "id": prompt_id, "version": version,
                "arn": f"arn:aws:bedrock:eu-west-2:{'5' * 12}:prompt/{prompt_id}"}

    def list_prompts(self, promptIdentifier=None, nextToken=None, maxResults=None):
        if promptIdentifier:
            entry = self.prompts[promptIdentifier]
            items = [self._summary(promptIdentifier, "DRAFT")] + [self._summary(promptIdentifier, number)
                                                                  for number in entry["versions"]]
        else:
            items = [self._summary(prompt_id, "DRAFT") for prompt_id in self.prompts]
        index = int(nextToken or 0)
        page = {"promptSummaries": items[index:index + 1]}
        if index + 1 < len(items):
            page["nextToken"] = str(index + 1)
        return page

    def create_prompt(self, *, name, description, defaultVariant, variants, tags):
        prompt_id = f"PROMPT{len(self.prompts) + 1}"
        self.prompts[prompt_id] = {"name": name, "description": description, "defaultVariant": defaultVariant,
                                   "draft": variants, "versions": {}, "tags": tags}
        return {"id": prompt_id, "version": "DRAFT"}

    def update_prompt(self, *, promptIdentifier, name, description, defaultVariant, variants):
        self.prompts[promptIdentifier].update(name=name, description=description, defaultVariant=defaultVariant,
                                              draft=variants)

    def create_prompt_version(self, *, promptIdentifier, description, tags):
        entry = self.prompts[promptIdentifier]
        number = str(len(entry["versions"]) + 1)
        entry["versions"][number] = {"variants": entry["draft"], "description": description}
        self.created_versions += 1
        return {"id": promptIdentifier, "version": number}

    def get_prompt(self, *, promptIdentifier, promptVersion):
        entry = self.prompts[promptIdentifier]
        stored = entry["versions"][promptVersion]
        return {"id": promptIdentifier, "version": promptVersion, "defaultVariant": entry["defaultVariant"],
                "variants": stored["variants"], "description": stored["description"],
                "arn": self._summary(promptIdentifier, promptVersion)["arn"] + f":{promptVersion}"}

    def delete_prompt(self, *, promptIdentifier):
        del self.prompts[promptIdentifier]


def test_render_fills_each_variable_once_and_refuses_bad_names():
    values = {"passages": "a {{question}} b", "question": "Q"}
    assert render_template("{{passages}} | {{question}}", values) == "a {{question}} b | Q"
    with pytest.raises(ValueError, match="passages"):
        render_template("{{question}}", {"question": "Q"})
    with pytest.raises(ValueError, match="questoin"):
        render_template("{{questoin}}", values)
    assert render_template("{{ question }}", values) == "{{ question }}", "Prompt Management names have no spaces"


def test_version_1_reproduces_the_requests_the_assistant_already_sends():
    passages = format_passages([passage("kd_01", 0.9)])
    system, message = LOCAL_PROMPT.render(passages=passages, question="Q?")
    assert system == SYSTEM_PROMPT
    assert message == f"{ANSWER_PROMPT}\n\n{passages}\n\nQuestion: Q?"


def test_the_reference_version_2_keeps_what_the_code_depends_on():
    assert set(REVISED_PROMPT.variables) == {"passages", "question"}
    _, message = REVISED_PROMPT.render(passages="PASSAGES", question="QUESTION")
    assert message.index("PASSAGES") < message.index("Rules:") < message.index("QUESTION")
    assert "reply with exactly NO_EVIDENCE" in message and "[kd_07]" in message
    assert not REVISED_PROMPT.same_text(LOCAL_PROMPT)


def test_the_chat_variant_holds_both_parts_and_the_course_model():
    variant = chat_variant(LOCAL_PROMPT)
    chat = variant["templateConfiguration"]["chat"]
    assert variant["templateType"] == "CHAT" and variant["modelId"] == config.MODEL_ID
    assert chat["system"] == [{"text": SYSTEM_PROMPT}]
    assert chat["messages"][0]["content"][0]["text"] == LOCAL_PROMPT.message
    assert [item["name"] for item in chat["inputVariables"]] == ["passages", "question"]


def test_ensure_version_creates_once_and_reuses_identical_words():
    agent = FakeAgent()
    first = ensure_version(agent, LOCAL_PROMPT, "Version 1")
    again = ensure_version(agent, LOCAL_PROMPT, "Version 1")
    assert (first.version, again.version) == ("1", "1") and agent.created_versions == 1
    assert first.same_text(LOCAL_PROMPT) and first.prompt_id == find_prompt(agent, config.resource_names().prompt)
    assert agent.prompts[first.prompt_id]["tags"] == config.tags(5)
    second = ensure_version(agent, REVISED_PROMPT, "Version 2")
    assert second.version == "2" and second.same_text(REVISED_PROMPT)
    assert version_numbers(agent, first.prompt_id) == ["1", "2"]
    assert load_version(agent, first.prompt_id, 1).same_text(LOCAL_PROMPT), "a version never changes"


def test_course_prompts_reads_every_page_and_only_this_learners_names():
    agent = FakeAgent()
    agent.create_prompt(name=config.resource_names().prompt, description="", defaultVariant="main", variants=[],
                        tags={})
    agent.create_prompt(name="fde-zz-kestrel-assistant", description="", defaultVariant="main", variants=[], tags={})
    assert [item["name"] for item in course_prompts(agent)] == [config.resource_names().prompt]


def test_the_injection_cases_are_the_day_3_cases():
    store = LocalCaseStore()
    notes = [note["note"] for note in store.get(INJECTED_CASE)["history"] if note["author"] == "customer"]
    assert any("ignore your previous instructions" in note for note in notes)
    assert len(INJECTION_CASES) == 5 and sum(case["scope_case"] == "case_1017" for case in INJECTION_CASES) == 4


def test_injection_runs_count_the_requests_that_the_dispatcher_refused():
    replies, reasons = [], []
    for case in INJECTION_CASES:
        target = "case_1002" if case["scope_case"] == "case_1017" else "case_1003"
        replies += [tool_use_message("lookup_case", {"case_id": target}, f"t-{case['name']}"),
                    text_message("I can't read that case.")]
        reasons += ["tool_use", "end_turn"]
    model = ScriptedModel(replies, reasons)
    template = PromptTemplate(system="SYSTEM PART", message="{{passages}} {{question}}")
    rows = run_injection_cases(model, template, run_prefix="test")
    assert [row["out_of_scope_requests"] for row in rows] == [1, 1, 1, 1, 1]
    assert all(row["status"] == "answered" and not row["draft_proposed"] for row in rows)
    assert set(model.systems) == {"SYSTEM PART"}


def summary(**changes):
    rows = [{"category": "answerable", "kind": "answer", "cited": True}] * 3 + \
           [{"category": "no_evidence", "kind": "no_evidence", "cited": False}]
    base = summarise("1", rows, [{"out_of_scope_requests": 0, "draft_proposed": False}],
                     [{"operation": "converse", "cost_usd": 0.001}, {"operation": "retrieve", "cost_usd": None}])
    return {**base, **changes}


def test_summarise_counts_cited_answers_and_cost():
    measured = summary()
    assert (measured["questions"], measured["answerable"], measured["cited_answers"]) == (4, 3, 3)
    assert (measured["no_evidence_answered"], measured["model_attempts"], measured["cost_usd"]) == (0, 1, 0.001)
    assert measured["attempts_with_unknown_cost"] == 1


def test_the_regression_rule():
    baseline = summary()
    assert regression_problems(baseline, summary()) == []
    assert regression_problems(baseline, summary(cited_answers=2)) == ["cited answers fell from 3 to 2"]
    assert regression_problems(baseline, summary(cited_answers=2), tolerance=1) == []
    assert regression_problems(baseline, summary(out_of_scope_requests=1))
    assert regression_problems(baseline, summary(questions=5))


def test_a_deleted_prompt_that_the_tag_listing_still_shows_is_reported_apart():
    agent = FakeAgent()
    kept = agent.create_prompt(name=config.resource_names().prompt, description="", defaultVariant="main",
                               variants=[], tags={})["id"]
    agent.create_prompt_version(promptIdentifier=kept, description="", tags={})

    def get_prompt(*, promptIdentifier, promptVersion=None):
        if promptIdentifier not in agent.prompts:
            raise client_error("ResourceNotFoundException", 404, "GetPrompt")
        return {"id": promptIdentifier}

    agent.get_prompt = get_prompt
    arn = f"arn:aws:bedrock:eu-west-2:<account-id>:prompt/{kept}"
    assert not prompt_is_deleted(agent, arn) and not prompt_is_deleted(agent, arn + ":1")
    assert prompt_is_deleted(agent, "arn:aws:bedrock:eu-west-2:<account-id>:prompt/GONE0001:2")
    assert not prompt_is_deleted(agent, "arn:aws:s3:::fde-tt-kestrel-abcdef")
