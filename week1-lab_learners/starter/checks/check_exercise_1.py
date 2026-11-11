"""Exercise 1 check: identity, the two read-only requests of Exercise 1.2, and the teardown record.

Run from the lab folder:  uv run --directory starter python -m pytest checks/check_exercise_1.py
The code checks always run. The record checks run when KESTREL_EVIDENCE names
your records folder, as the workbook's check cell sets it.
"""

from __future__ import annotations

import pytest
from kestrel_evidence import read_json, secrets_in

from support_assistant import config

ACCOUNT = "3" * 12


def test_describe_identity_reads_an_iam_user():
    record = config.describe_identity(f"arn:aws:iam::{ACCOUNT}:user/fde-learner-ab")
    assert record.principal_kind == "user"
    assert record.principal_name == "fde-learner-ab"
    assert record.account == "<account-id>"


def test_describe_identity_reads_an_assumed_role_and_its_session():
    record = config.describe_identity(f"arn:aws:sts::{ACCOUNT}:assumed-role/AWSReservedSSO_FdeLearner_0a1b/ab")
    assert (record.service, record.principal_kind) == ("sts", "assumed-role")
    assert (record.principal_name, record.session_name) == ("AWSReservedSSO_FdeLearner_0a1b", "ab")


def test_describe_identity_never_returns_the_account_number():
    record = config.describe_identity(f"arn:aws:sts::{ACCOUNT}:assumed-role/Role/session")
    assert ACCOUNT not in str(record.as_record())


def test_describe_identity_refuses_text_that_is_not_an_arn():
    with pytest.raises(ValueError):
        config.describe_identity("not an arn")


def test_evidence_identity_record(evidence):
    identity = read_json(evidence, "day1-identity.json")
    for key in ("principal_kind", "principal_name", "account", "account_alias", "region", "aws_cli_version"):
        assert key in identity, f"the identity record has no {key}"
    assert identity["account"] == "<account-id>"
    assert identity["region"] in config.POLICY_REGIONS


def test_evidence_allowed_and_denied_calls(evidence):
    calls = read_json(evidence, "day1-calls.json")
    assert calls["allowed"]["returncode"] == 0, "the model listing in London failed; read its error in day1-calls.json"
    assert config.BASE_MODEL_ID in calls["allowed"]["stdout"], "the course model is not in the London listing"
    # The example learner policy refuses the guardrail listing in Ireland. An account under other policies
    # may allow it, and that result is correct too. A failure for any reason other than a refusal is not.
    ireland = calls["denied"]
    if ireland["returncode"] != 0:
        assert ireland["error_code"] == "AccessDeniedException", (
            f"the guardrail listing in Ireland failed with {ireland['error_code']}, not with a permission refusal; "
            "read its error in day1-calls.json, then run the Exercise 1.2 cell again")


def test_evidence_teardown_record(evidence):
    teardown = read_json(evidence, "day1-teardown.json")
    assert set(teardown["tags"]) == {"course", "lab", "owner"}
    assert teardown["listed_before_delete"], "the tag listing before deletion should show the bucket"
    for region in config.POLICY_REGIONS:
        assert teardown["listed_after_delete"][region] == [], f"something is still tagged in {region}"


def test_evidence_holds_no_account_number_or_key(evidence):
    assert secrets_in(evidence) == []
