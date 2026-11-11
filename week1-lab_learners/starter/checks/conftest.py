"""Configure the exercise checks with a separate temporary work folder per test and AWS calls disabled.

Run a check from the folder of the version you are working on, so that it tests
that version's `support_assistant`. The first line of the output names it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import support_assistant  # noqa: E402
from support_assistant import config  # noqa: E402


def pytest_report_header():
    package = Path(support_assistant.__file__).resolve().parent
    try:
        shown = package.relative_to(support_assistant.config.LABS_DIR)
    except ValueError:
        shown = package
    return f"package under test: {shown}"


@pytest.fixture(autouse=True)
def isolated_work(tmp_path, monkeypatch):
    if not (os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")):
        monkeypatch.setenv("AWS_DEFAULT_REGION", config.POLICY_REGIONS[0])
    monkeypatch.setenv("FDE_OWNER", "tt")
    work = tmp_path / "work"
    monkeypatch.setattr(config, "WORK_DIR", work)
    monkeypatch.setattr(config, "STATE_FILE", work / "state.json")
    monkeypatch.setattr(config, "LEDGER_FILE", work / "calls.jsonl")
    monkeypatch.setattr(config, "RUN_LOG_FILE", work / "runlog.jsonl")
    yield work


@pytest.fixture
def evidence() -> Path:
    """Return the records folder named by KESTREL_EVIDENCE, or skip the record checks.

    The workbook's check cells set the variable to `work/evidence/<initials>/`.
    Without it, only the code is checked.
    """
    value = os.environ.get("KESTREL_EVIDENCE")
    if not value:
        pytest.skip("KESTREL_EVIDENCE is not set, so only the code is checked")
    folder = Path(value)
    assert folder.is_dir(), f"the evidence folder {folder} does not exist"
    return folder
