"""Exercise 5, part one, check: the retrieval measure, cited answers and the comparison.

Run from the lab folder:
    uv run --directory starter/exercise-5-part-1 python -m pytest ../checks/check_exercise_5_part_1.py
The code checks always run. The record checks run when KESTREL_EVIDENCE names
your records folder, as the workbook's check cell sets it. The scripted model
tests the supplied answer function's checks; it is never evidence of what a
model does.
"""

from __future__ import annotations

from kestrel_doubles import ScriptedModel, passage, text_message
from kestrel_evidence import read_json

from support_assistant.assistant import answer_from_passages
from support_assistant.retrieval import hit_at


def test_hit_at():
    assert hit_at({"kd_02"}, ["kd_02", "kd_05"], 1) is True
    assert hit_at({"kd_02"}, ["kd_05", "kd_04", "kd_02"], 2) is False
    assert hit_at(set(), ["kd_05"], 5) is None


def test_a_cited_answer_is_matched_to_the_passages_supplied():
    supplied = [passage("kd_01", 0.9)]
    manifest = {"kd_01": {"status": "current"}}

    def answer(text):
        model = ScriptedModel([text_message(text)], ["end_turn"])
        return answer_from_passages(model, "Can I call support on a Sunday?", supplied, manifest, run_id="r-ex5")

    cited = answer("Yes, the support line is open every day [kd_01].")
    assert cited.kind == "answer" and [citation.doc_id for citation in cited.citations] == ["kd_01"]
    assert cited.citations[0].location == supplied[0].location, "a citation's location comes from its passage"
    assert answer("Yes, every day [kd_05].").kind == "refused", "a citation of a passage not supplied is refused"
    assert answer("Yes, every day.").kind == "refused", "an answer that cites nothing is refused"
    assert answer("NO_EVIDENCE").kind == "no_evidence"


def test_evidence_retrieval_comparison(evidence):
    comparison = read_json(evidence, "day4-retrieval-comparison.json")
    assert comparison["answerable_questions"] == 25 and comparison["top_k"] == 5
    for name in ("baseline", "knowledge_base"):
        assert 0.0 <= comparison[name]["hit_rate_top_k"] <= 1.0
    assert len(comparison["no_evidence_top_scores"]) == 5


def test_evidence_cited_answers(evidence):
    answers = read_json(evidence, "day4-cited-answers.json")
    cited = [item for item in answers if item["kind"] == "answer" and item["citations"]]
    assert len(cited) >= 3, "keep at least three answers whose citations passed the check"
