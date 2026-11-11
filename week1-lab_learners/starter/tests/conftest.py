"""Configure offline tests with AWS calls disabled and a separate temporary work folder per test."""

from __future__ import annotations

import os

import pytest

from support_assistant import config


@pytest.fixture(autouse=True)
def isolated_work(tmp_path, monkeypatch):
    """Point every record at a temporary folder and give the code a Region and an owner.

    `tools/check_workbook.py` runs these suites with every AWS credential removed.
    The Region still has to come from somewhere for boto3 to build a client, so a
    test uses the shell's value, or the course Region when the shell has none.
    """
    if not (os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")):
        monkeypatch.setenv("AWS_DEFAULT_REGION", config.POLICY_REGIONS[0])
    monkeypatch.setenv("FDE_OWNER", "tt")
    work = tmp_path / "work"
    monkeypatch.setattr(config, "WORK_DIR", work)
    monkeypatch.setattr(config, "STATE_FILE", work / "state.json")
    monkeypatch.setattr(config, "LEDGER_FILE", work / "calls.jsonl")
    monkeypatch.setattr(config, "RUN_LOG_FILE", work / "runlog.jsonl")
    yield work
