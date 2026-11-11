"""The prompt regression test of Exercise 5, part two.

The test compares two saved runs of the assistant's prompt on the course
question set and the Day 3 injection cases: a baseline version and a candidate
version. It fails when the candidate gives fewer cited answers than the
baseline, or when the model asks for more cases outside the caller's scope.
The test reports its result; it does not select or deploy a prompt version.
The team keeps a failed candidate out of use and reviews its changed answers.

Run it from the version supplied for the exercise, after the workbook has saved
both runs:

    cd starter/exercise-5-part-2
    KESTREL_EVIDENCE=../../work/evidence/<initials> KESTREL_CANDIDATE_VERSION=2 \\
        uv run python -m pytest ../checks/prompt_regression.py

`KESTREL_BASELINE_VERSION` is 1 unless you set it, and `KESTREL_CANDIDATE_VERSION`
is the highest saved version. `KESTREL_TOLERANCE` is the number of cited
answers that the candidate may lose before the test fails; it is 0 unless you
set it from the variation you have measured between runs of one version.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from kestrel_evidence import read_json

from support_assistant.prompts import regression_problems

PREFIX = "day5-prompt-version-"


def records_folder() -> Path:
    value = os.environ.get("KESTREL_EVIDENCE")
    if not value:
        pytest.fail("set KESTREL_EVIDENCE to your records folder, work/evidence/<initials>")
    return Path(value).resolve()


def test_the_candidate_version_keeps_its_cited_answers():
    folder = records_folder()
    saved = sorted(int(path.stem.removeprefix(PREFIX)) for path in folder.glob(f"{PREFIX}*.json"))
    assert saved, f"no saved runs in {folder}; run the versions in the workbook first"
    baseline = os.environ.get("KESTREL_BASELINE_VERSION", "1")
    candidate = os.environ.get("KESTREL_CANDIDATE_VERSION") or str(saved[-1])
    assert candidate != baseline, "name a candidate version other than the baseline"
    before = read_json(folder, f"{PREFIX}{baseline}.json")["summary"]
    after = read_json(folder, f"{PREFIX}{candidate}.json")["summary"]
    problems = regression_problems(before, after, tolerance=int(os.environ.get("KESTREL_TOLERANCE", "0")))
    assert problems == [], f"version {candidate} against version {baseline}: " + "; ".join(problems)
