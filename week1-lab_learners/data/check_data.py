#!/usr/bin/env python3
"""Check the Kestrel Telecom dataset against the schemas in README.md.

The script validates every file in this folder and confirms that the dataset
still contains the deliberate defects that the lab exercises use.
It exits with status 0 when everything passes and with status 1 otherwise.

By default it prints counts only, so a learner can run it without learning
which record or document is defective. The identities of the defects live in
the staff-only `planted-defects-assessor-guide.md`, which the learner package
leaves out. When that guide is beside this script, the default run also
confirms each defect's identity, still printing counts only.

Run it with Python 3.12 or later. It uses the standard library only and makes
no network calls.

    python3 check_data.py              # validate; print counts only
    python3 check_data.py --staff      # validate; name each defect (needs the guide)
    python3 check_data.py --self-test  # remove each defect in memory and confirm
                                       # that the check then fails (needs the guide)
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent
GUIDE_NAME = "planted-defects-assessor-guide.md"
REFERENCE_DATE = date(2026, 10, 31)
MAX_DOCUMENT_AGE_DAYS = 365

PLANS = {"essential_80", "fibre_300", "fibre_900", "business_500"}
TEAMS = {"customer_care", "technical_support", "billing"}
STATUSES = {"open", "in_progress", "awaiting_customer", "awaiting_engineer", "resolved", "closed"}
AUTHORS = TEAMS | {"customer", "system"}
AUDIENCES = {"customer", "internal"}
DOCUMENT_STATUSES = {"current", "superseded"}
HEADER_KEYS = ("Last reviewed", "Document id", "Owner team", "Audience", "Status")
ROLES = {"customer", "first_line_agent", "supervisor", "auditor"}
SCOPES = {
    "read_own_cases", "read_team_cases", "read_all_cases",
    "read_customer_documents", "read_internal_documents",
    "draft_reply", "apply_goodwill_credit", "request_credit_approval",
    "approve_goodwill_credit", "read_audit_trail",
}
TOOLS = ("lookup_case", "draft_reply")
CATEGORY_COUNTS = {
    "answerable": 20, "no_evidence": 5, "contradicted": 2, "out_of_date": 1, "out_of_scope": 2,
}
CASE_FIELDS = (
    "case_id", "customer_id", "customer_name", "plan", "status",
    "opened_at", "owner_team", "summary", "history", "postcode_area",
)
QUESTION_FIELDS = (
    "question_id", "asked_by", "question", "reference_answer", "supporting_documents",
    "misleading_documents", "case_id", "expected_tools", "assertions", "category",
)
USER_FIELDS = (
    "user_id", "display_name", "role", "email", "customer_id", "team",
    "goodwill_credit_limit_pence", "scopes",
)
EXPECTED_RECORDS = 40
EXPECTED_DOCUMENTS = 25

# How many defects of each kind the labs expect. The identities are in the guide.
EXPECTED_DEFECT_COUNTS = {
    "contract": 1,      # records that break the case contract
    "repeated": 1,      # case ids that appear twice
    "stale": 1,         # documents that are superseded and past the freshness limit
    "injected": 1,      # cases with a note that addresses an assistant
}

# Terms that the no-evidence questions ask about. None may appear in the corpus,
# or the question would stop being a no-evidence question.
NO_EVIDENCE_TERMS = {
    "kq_03": r"ipv6",
    "kq_11": r"\bon hold\b|\bpaus",
    "kq_16": r"\bstudent",
    "kq_22": r"wi-?fi\s*[0-9]",
    "kq_29": r"\btv\b|television",
}

ISO_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CASE_ID = re.compile(r"^case_\d{4}$")
CUSTOMER_ID = re.compile(r"^cust_\d{4}$")
QUESTION_ID = re.compile(r"^kq_\d{2}$")
USER_ID = re.compile(r"^user_[a-z]+_\d{2}$")
POSTCODE_AREA = re.compile(r"^KT-0[1-9]$")
DOC_FILE = re.compile(r"^kd-(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
# A general screen for text that tries to instruct an assistant, of the kind a
# real ingestion pipeline would run. It doesn't name any record.
INJECTION = re.compile(
    r"(?i)\b(?:ignore|disregard)\b[^.]{0,60}\binstructions\b|\bAI assistant\b"
)
GUIDE_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)

# Synthetic-data screens.
PHONE = re.compile(r"(?<![\d.£])(?:\+44\s?|0)\d(?:[ -]?\d){8,9}(?!\d)")
ALLOWED_PHONE = re.compile(r"^01632960\d{3}$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
ALLOWED_EMAIL_DOMAINS = {"kestrel.example", "example.com"}
UK_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b")
URL_HOST = re.compile(r"https?://([^/\s)\"'`>]+)")
ALLOWED_URL_HOSTS = {"aws.amazon.com", "docs.aws.amazon.com"}
AWS_ACCOUNT_ID = re.compile(r"(?<![\d.])\d{12}(?![\d.])")
ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
ARN = re.compile(r"\barn:aws")


class Findings:
    """Problems and results. Details that name a defect are shown only with --staff."""

    def __init__(self) -> None:
        self.problems: list[tuple[str, str | None]] = []
        self.counts: dict[str, object] = {}
        self.names: dict[str, str] = {}

    def fail(self, message: str, detail: str | None = None) -> None:
        self.problems.append((message, detail))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load(folder: Path) -> dict:
    """Read every file in the dataset, and the staff guide if it is present."""
    documents = {}
    for path in sorted((folder / "documents").glob("*")):
        if path.is_file():
            documents[path.name] = path.read_text(encoding="utf-8")
    dataset = {"documents": documents, "texts": {}, "guide": None}
    for name in ("cases.json", "users.json", "approval-case.json", "questions.json", "pricing.json"):
        text = (folder / name).read_text(encoding="utf-8")
        dataset["texts"][name] = text
        dataset[name] = json.loads(text)
    for name in ("README.md", "kestrel-company.md"):
        dataset["texts"][name] = (folder / name).read_text(encoding="utf-8")
    guide = folder / GUIDE_NAME
    if guide.is_file():
        text = guide.read_text(encoding="utf-8")
        dataset["texts"][GUIDE_NAME] = text
        block = GUIDE_BLOCK.search(text)
        if not block:
            raise ValueError(f"{GUIDE_NAME} has no JSON defect list")
        dataset["guide"] = json.loads(block.group(1))
    return dataset


def parse_document(name: str, text: str, out: Findings) -> dict | None:
    """Parse one corpus document's header and body, recording format problems."""
    match = DOC_FILE.match(name)
    if not match:
        out.fail(f"documents/{name}: the filename is not kd-NN-<kebab-case-title>.md")
        return None
    lines = text.splitlines()
    if len(lines) < 9 or not lines[0].startswith("# ") or lines[1] != "":
        out.fail(f"documents/{name}: the file does not start with a '# ' title and a blank line")
        return None
    header = {}
    for line, key in zip(lines[2:7], HEADER_KEYS):
        prefix = f"{key}: "
        if not line.startswith(prefix):
            out.fail(f"documents/{name}: expected a '{prefix}' line, found {line!r}")
            return None
        header[key] = line[len(prefix):].strip()
    if lines[7] != "":
        out.fail(f"documents/{name}: the header must end with a blank line")
    doc_id = header["Document id"]
    if doc_id != f"kd_{match.group(1)}":
        out.fail(f"documents/{name}: Document id {doc_id} does not match the filename")
    if not ISO_DATE.match(header["Last reviewed"]):
        out.fail(f"documents/{name}: Last reviewed is not YYYY-MM-DD")
        return None
    if header["Owner team"] not in TEAMS:
        out.fail(f"documents/{name}: Owner team {header['Owner team']!r} is not a team")
    if header["Audience"] not in AUDIENCES:
        out.fail(f"documents/{name}: Audience {header['Audience']!r} is not customer or internal")
    if header["Status"] not in DOCUMENT_STATUSES:
        out.fail(f"documents/{name}: Status {header['Status']!r} is not current or superseded")
    body = "\n".join(lines[8:])
    words = len(re.findall(r"\S+", body))
    if not 150 <= words <= 400:
        out.fail(f"documents/{name}: the body has {words} words, outside 150 to 400")
    return {
        "doc_id": doc_id,
        "file": name,
        "title": lines[0][2:].strip(),
        "last_reviewed": date.fromisoformat(header["Last reviewed"]),
        "owner_team": header["Owner team"],
        "audience": header["Audience"],
        "status": header["Status"],
        "body": body,
    }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_documents(ds: dict, out: Findings) -> dict:
    docs = {}
    for name, text in ds["documents"].items():
        parsed = parse_document(name, text, out)
        if parsed:
            if parsed["doc_id"] in docs:
                out.fail(f"documents/{name}: duplicate Document id {parsed['doc_id']}")
            docs[parsed["doc_id"]] = parsed
    if len(ds["documents"]) != EXPECTED_DOCUMENTS:
        out.fail(f"documents/: expected {EXPECTED_DOCUMENTS} files, found {len(ds['documents'])}")

    # Freshness and status must agree: a current document is inside the limit,
    # and a superseded one is outside it.
    stale = sorted(
        d for d, doc in docs.items()
        if (REFERENCE_DATE - doc["last_reviewed"]).days > MAX_DOCUMENT_AGE_DAYS
    )
    superseded = sorted(d for d, doc in docs.items() if doc["status"] == "superseded")
    future = sorted(d for d, doc in docs.items() if doc["last_reviewed"] > REFERENCE_DATE)
    if future:
        out.fail(f"documents: Last reviewed is after the reference date in {future}")
    if stale != superseded:
        out.fail("documents: the superseded documents and the documents past the freshness limit differ",
                 f"superseded {superseded}, past the limit {stale}")
    if len(stale) != EXPECTED_DEFECT_COUNTS["stale"]:
        out.fail(f"documents: expected {EXPECTED_DEFECT_COUNTS['stale']} superseded document past the "
                 f"freshness limit, found {len(stale)}", f"{stale}")
    out.counts["stale"] = len(stale)
    ds["_stale"] = stale

    corpus = "\n".join(doc["body"] + "\n" + doc["title"] for doc in docs.values()).lower()
    for question_id, pattern in NO_EVIDENCE_TERMS.items():
        if re.search(pattern, corpus):
            out.fail(f"documents: the corpus now mentions what {question_id} asks about ({pattern})")
    out.counts["documents"] = (
        f"{len(docs)} documents, {sum(d['audience'] == 'internal' for d in docs.values())} internal, "
        f"{len(superseded)} superseded"
    )
    return docs


def case_problems(record: dict) -> list[str]:
    """Return the contract violations in one case record."""
    reasons = []
    for field in CASE_FIELDS:
        if field not in record or record[field] in (None, "", []):
            reasons.append(f"missing required field {field}")
    extra = set(record) - set(CASE_FIELDS)
    if extra:
        reasons.append(f"unknown fields {sorted(extra)}")
    if "case_id" in record and not CASE_ID.match(str(record["case_id"])):
        reasons.append("case_id does not match case_NNNN")
    if "customer_id" in record and not CUSTOMER_ID.match(str(record["customer_id"])):
        reasons.append("customer_id does not match cust_NNNN")
    if record.get("plan") and record["plan"] not in PLANS:
        reasons.append(f"plan {record['plan']!r} is not a Kestrel plan")
    if record.get("owner_team") and record["owner_team"] not in TEAMS:
        reasons.append(f"owner_team {record['owner_team']!r} is not a team")
    if record.get("status") and record["status"] not in STATUSES:
        reasons.append(f"status {record['status']!r} is not a case status")
    if record.get("postcode_area") and not POSTCODE_AREA.match(str(record["postcode_area"])):
        reasons.append("postcode_area is not KT-01 to KT-09")
    opened = record.get("opened_at")
    if opened and not ISO_INSTANT.match(str(opened)):
        reasons.append("opened_at is not ISO 8601")
    history = record.get("history")
    if history is not None:
        if not isinstance(history, list):
            reasons.append("history is not a list")
        else:
            previous = None
            for index, item in enumerate(history):
                if not isinstance(item, dict) or set(item) != {"at", "author", "note"}:
                    reasons.append(f"history[{index}] does not have exactly at, author and note")
                    continue
                if not ISO_INSTANT.match(str(item["at"])):
                    reasons.append(f"history[{index}].at is not ISO 8601")
                elif previous and item["at"] < previous:
                    reasons.append(f"history[{index}] is earlier than the note before it")
                else:
                    previous = item["at"]
                if item["author"] not in AUTHORS:
                    reasons.append(f"history[{index}].author {item['author']!r} is not allowed")
                if not str(item["note"]).strip():
                    reasons.append(f"history[{index}].note is empty")
            if (
                opened and ISO_INSTANT.match(str(opened)) and history
                and isinstance(history[0], dict) and str(history[0].get("at", "")) < opened
            ):
                reasons.append("the first history note is earlier than opened_at")
    return reasons


def check_cases(ds: dict, out: Findings) -> dict:
    data = ds["cases.json"]
    if data.get("synthetic") is not True:
        out.fail("cases.json: synthetic must be true")
    records = data.get("cases", [])
    if len(records) != EXPECTED_RECORDS:
        out.fail(f"cases.json: expected {EXPECTED_RECORDS} records, found {len(records)}")

    invalid = {}
    for index, record in enumerate(records):
        reasons = case_problems(record)
        if reasons:
            invalid[record.get("case_id", f"record {index + 1}")] = sorted(set(reasons))
    if len(invalid) != EXPECTED_DEFECT_COUNTS["contract"]:
        out.fail(f"cases.json: expected {EXPECTED_DEFECT_COUNTS['contract']} record to break the case "
                 f"contract, found {len(invalid)}", f"{invalid}")
    out.counts["contract"] = len(invalid)
    ds["_invalid"] = invalid

    counts = Counter(r.get("case_id") for r in records)
    repeated = {k: v for k, v in counts.items() if v > 1}
    if len(repeated) != EXPECTED_DEFECT_COUNTS["repeated"] or any(v != 2 for v in repeated.values()):
        out.fail(f"cases.json: expected {EXPECTED_DEFECT_COUNTS['repeated']} case id to appear exactly "
                 f"twice, found {len(repeated)}", f"{repeated}")
    for case_id in repeated:
        copies = [r for r in records if r.get("case_id") == case_id]
        if any(c != copies[0] for c in copies):
            out.fail("cases.json: the repeated records are not identical copies", case_id)
    out.counts["repeated"] = len(repeated)
    ds["_repeated"] = {
        k: [i + 1 for i, r in enumerate(records) if r.get("case_id") == k] for k in repeated
    }

    injected = sorted({
        r.get("case_id") for r in records
        for item in r.get("history", []) if isinstance(item, dict)
        if INJECTION.search(str(item.get("note", "")))
    })
    if len(injected) != EXPECTED_DEFECT_COUNTS["injected"]:
        out.fail(f"cases.json: expected {EXPECTED_DEFECT_COUNTS['injected']} case with a note that "
                 f"addresses an assistant, found {len(injected)}", f"{injected}")
    out.counts["injected"] = len(injected)
    ds["_injected"] = injected

    valid = {}
    for record in records:
        if record.get("case_id") not in invalid:
            valid.setdefault(record["case_id"], record)
    for field, allowed in (("plan", PLANS), ("owner_team", TEAMS)):
        spread = Counter(r[field] for r in valid.values())
        thin = sorted(v for v in allowed if spread[v] < 5)
        if thin:
            out.fail(f"cases.json: fewer than five valid cases for {field} {thin}")
    customers = {}
    for record in records:
        key = record.get("customer_id")
        value = (record.get("customer_name"), record.get("postcode_area"))
        if key in customers and customers[key] != value:
            out.fail(f"cases.json: {key} has different names or areas in different records")
        customers.setdefault(key, value)
    out.counts["cases"] = f"{len(records)} records, {len(counts)} distinct case ids"
    return valid


def check_users(ds: dict, cases: dict, out: Findings) -> dict:
    data = ds["users.json"]
    if data.get("synthetic") is not True:
        out.fail("users.json: synthetic must be true")
    users = {}
    for user in data.get("users", []):
        missing = [f for f in USER_FIELDS if f not in user]
        if missing:
            out.fail(f"users.json: {user.get('user_id')} is missing {missing}")
            continue
        if not USER_ID.match(user["user_id"]):
            out.fail(f"users.json: {user['user_id']} does not match user_<role>_NN")
        if user["role"] not in ROLES:
            out.fail(f"users.json: {user['user_id']} has unknown role {user['role']!r}")
        unknown = set(user["scopes"]) - SCOPES
        if unknown:
            out.fail(f"users.json: {user['user_id']} has unknown scopes {sorted(unknown)}")
        if user["team"] is not None and user["team"] not in TEAMS:
            out.fail(f"users.json: {user['user_id']} has unknown team {user['team']!r}")
        if "read_team_cases" in user["scopes"] and user["team"] is None:
            out.fail(f"users.json: {user['user_id']} reads team cases but has no team")
        if "read_own_cases" in user["scopes"] and \
                user["customer_id"] not in {c["customer_id"] for c in cases.values()}:
            out.fail(f"users.json: {user['user_id']} has a customer_id with no cases")
        if not isinstance(user["goodwill_credit_limit_pence"], int):
            out.fail(f"users.json: {user['user_id']} goodwill_credit_limit_pence is not an integer")
        users[user["user_id"]] = user
    roles = Counter(u["role"] for u in users.values())
    if roles != Counter({r: 1 for r in ROLES}):
        out.fail(f"users.json: expected one user for each of {sorted(ROLES)}, found {dict(roles)}")
    defined = {d.get("scope") for d in data.get("scope_definitions", [])}
    if defined != SCOPES:
        out.fail(f"users.json: scope_definitions do not define exactly {sorted(SCOPES)}")
    return users


def can_read(user: dict, case: dict) -> bool:
    """Apply the case-reading scopes from users.json to one case."""
    scopes = set(user["scopes"])
    if "read_all_cases" in scopes:
        return True
    if "read_team_cases" in scopes and case["owner_team"] == user["team"]:
        return True
    if "read_own_cases" in scopes and case["customer_id"] == user["customer_id"]:
        return True
    return False


def check_approval(ds: dict, cases: dict, users: dict, docs: dict, out: Findings) -> None:
    data = ds["approval-case.json"]
    required = (
        "synthetic", "approval_id", "case_id", "customer_id", "related_case_ids", "owner_team",
        "submitted_at", "requested_by", "approver_role", "policy_document", "request",
        "evidence_available", "evidence_missing", "supplementary_evidence", "decision_states",
        "initial_state",
    )
    missing = [k for k in required if k not in data]
    if missing:
        out.fail(f"approval-case.json: missing {missing}")
        return
    # The learner decides the outcome from the evidence, so the data file must
    # not carry the answer. The staff guide records the expected outcome.
    oracle_keys = sorted(k for k in data if k.startswith("expected"))
    if oracle_keys:
        out.fail(f"approval-case.json: contains the Day 9 answer {oracle_keys}, which belongs in the staff guide")
    case = cases.get(data["case_id"])
    if case is None:
        out.fail(f"approval-case.json: case {data['case_id']} is not a valid case")
        return
    if case["customer_id"] != data["customer_id"] or case["owner_team"] != data["owner_team"]:
        out.fail("approval-case.json: customer_id or owner_team does not match the case")
    for related in data["related_case_ids"]:
        if related not in cases or cases[related]["customer_id"] != data["customer_id"]:
            out.fail(f"approval-case.json: related case {related} is not the same customer's case")
    requester = users.get(data["requested_by"])
    approvers = [u for u in users.values() if u["role"] == data["approver_role"]]
    amount = data["request"].get("amount_pence")
    if not requester or not approvers or not isinstance(amount, int):
        out.fail("approval-case.json: requester, approver role or amount_pence is not valid")
        return
    approver = approvers[0]
    if not requester["goodwill_credit_limit_pence"] < amount <= approver["goodwill_credit_limit_pence"]:
        out.fail("approval-case.json: the amount must exceed the requester's limit and fit the approver's")
    if approver["team"] != case["owner_team"]:
        out.fail("approval-case.json: the approver's team does not own the case")
    states = {s["state"]: s for s in data["decision_states"]}
    for state in states.values():
        for target in state["next_states"]:
            if target not in states:
                out.fail(f"approval-case.json: {state['state']} leads to undefined state {target}")
    if data["initial_state"] not in states:
        out.fail(f"approval-case.json: initial state {data['initial_state']} is not defined")
    missing_ids = {e["evidence_id"] for e in data["evidence_missing"]}
    supplied_ids = {e["evidence_id"] for e in data["supplementary_evidence"]}
    if missing_ids != supplied_ids:
        out.fail("approval-case.json: supplementary evidence does not answer every missing item")
    if data["policy_document"] not in docs:
        out.fail("approval-case.json: policy_document is not a corpus document")
    out.counts["approval"] = (
        f"{data['approval_id']} on {data['case_id']}, £{amount / 100:.2f}, "
        f"{len(states)} decision states"
    )



def check_questions(ds: dict, docs: dict, cases: dict, users: dict, out: Findings) -> None:
    data = ds["questions.json"]
    if data.get("synthetic") is not True:
        out.fail("questions.json: synthetic must be true")
    if tuple(data.get("tools", ())) != TOOLS:
        out.fail(f"questions.json: tools must be {list(TOOLS)}")
    questions = data.get("questions", [])
    if len(questions) != 30:
        out.fail(f"questions.json: expected 30 questions, found {len(questions)}")
    superseded = {d for d, doc in docs.items() if doc["status"] == "superseded"}
    seen = set()
    categories = Counter()
    out_of_scope = []
    contradicted_support = []
    empty_support = 0
    for item in questions:
        qid = item.get("question_id", "?")
        where = f"questions.json: {qid}"
        if set(item) != set(QUESTION_FIELDS):
            out.fail(f"{where} does not have exactly the fields {list(QUESTION_FIELDS)}")
            continue
        if not QUESTION_ID.match(qid) or qid in seen:
            out.fail(f"{where} has a malformed or repeated question_id")
        seen.add(qid)
        category = item["category"]
        categories[category] += 1
        if category not in CATEGORY_COUNTS:
            out.fail(f"{where} has unknown category {category!r}")
        user = users.get(item["asked_by"])
        if user is None:
            out.fail(f"{where} is asked by unknown user {item['asked_by']!r}")
            continue
        for doc_id in item["supporting_documents"] + item["misleading_documents"]:
            if doc_id not in docs:
                out.fail(f"{where} names unknown document {doc_id}")
        support = item["supporting_documents"]
        if not support:
            empty_support += 1
        if (category == "no_evidence") != (not support):
            out.fail(f"{where}: only no_evidence questions may have no supporting document")
        for doc_id in support:
            if doc_id not in item["reference_answer"]:
                out.fail(f"{where}: the reference answer does not name {doc_id}")
            if doc_id in docs and docs[doc_id]["audience"] == "internal" and \
                    "read_internal_documents" not in user["scopes"]:
                out.fail(f"{where}: cites internal document {doc_id} for a user who cannot read it")
            if doc_id in superseded:
                out.fail(f"{where}: cites a superseded document as support")
        tools = item["expected_tools"]
        if any(t not in TOOLS for t in tools) or len(tools) != len(set(tools)):
            out.fail(f"{where}: expected_tools must be distinct names from {list(TOOLS)}")
        if "draft_reply" in tools and tools[:1] != ["lookup_case"]:
            out.fail(f"{where}: draft_reply must come after lookup_case")
        if ("lookup_case" in tools) != (item["case_id"] is not None):
            out.fail(f"{where}: case_id and lookup_case must appear together")
        if "draft_reply" in tools and "draft_reply" not in user["scopes"]:
            out.fail(f"{where}: the asking user cannot draft replies")
        assertions = item["assertions"]
        if not 1 <= len(assertions) <= 3 or not all(
            isinstance(a, str) and a.strip().endswith(".") for a in assertions
        ):
            out.fail(f"{where}: needs one to three assertions written as full sentences")
        if item["case_id"] is not None:
            case = cases.get(item["case_id"])
            if case is None:
                out.fail(f"{where}: {item['case_id']} is not a valid case")
            else:
                readable = can_read(user, case)
                if category == "out_of_scope":
                    if readable:
                        out.fail(f"{where}: the case is inside the asking user's scope")
                    else:
                        out_of_scope.append(qid)
                elif not readable:
                    out.fail(f"{where}: the case is outside the asking user's scope")
        if category == "contradicted":
            if len(support) < 2:
                out.fail(f"{where}: a contradicted question must cite at least two documents")
            contradicted_support.append(set(support))
        if category == "out_of_date" and not set(item["misleading_documents"]) & superseded:
            out.fail(f"{where}: an out_of_date question must list a superseded document as misleading")
    if dict(categories) != CATEGORY_COUNTS:
        out.fail(f"questions.json: category counts {dict(categories)} differ from {CATEGORY_COUNTS}")
    if empty_support != CATEGORY_COUNTS["no_evidence"]:
        out.fail(f"questions.json: {empty_support} questions have no supporting document, expected 5")
    if len(out_of_scope) != CATEGORY_COUNTS["out_of_scope"]:
        out.fail(f"questions.json: expected {CATEGORY_COUNTS['out_of_scope']} questions about a case "
                 f"outside the asker's scope, found {len(out_of_scope)}")
    shared = set.intersection(*contradicted_support) if contradicted_support else set()
    if len(shared) < 2:
        out.fail("questions.json: the contradicted questions must cite the same pair of documents")
    ds["_contradicted_docs"] = sorted(shared)
    ds["_out_of_scope"] = out_of_scope
    if ds.get("_injected") and not any(q.get("case_id") in ds["_injected"] for q in questions):
        out.fail("questions.json: no question exercises the case note that addresses an assistant")
    out.counts["out_of_scope"] = len(out_of_scope)
    out.counts["contradicted"] = categories["contradicted"]
    out.counts["questions"] = ", ".join(f"{k} {v}" for k, v in sorted(categories.items()))


def check_pricing(ds: dict, out: Findings) -> None:
    data = ds["pricing.json"]
    source = data.get("source", {})
    if not str(source.get("url", "")).startswith("https://aws.amazon.com/bedrock/pricing"):
        out.fail("pricing.json: source.url must be the Amazon Bedrock pricing page")
    if not ISO_DATE.match(str(source.get("read_on", ""))):
        out.fail("pricing.json: source.read_on must be YYYY-MM-DD")
    if data.get("region") != "eu-west-2" or data.get("unit") != "per_million_tokens":
        out.fail("pricing.json: region must be eu-west-2 and unit per_million_tokens")
    profiles = {}
    for model in data.get("models", []):
        profiles[model.get("inference_profile_id")] = model
        for key in ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read"):
            if not isinstance(model.get(key), (int, float)) or model[key] <= 0:
                out.fail(f"pricing.json: {model.get('model_name')} has no positive {key} price")
    wanted = {
        "eu.anthropic.claude-haiku-4-5-20251001-v1:0", "eu.anthropic.claude-sonnet-4-6",
        "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "eu.anthropic.claude-haiku-5-5", "eu.anthropic.claude-sonnet-5-5",
    }
    if set(profiles) != wanted:
        out.fail(f"pricing.json: models must be exactly {sorted(wanted)}")
        return
    chosen = {}
    for key in ("course_model", "comparison_model"):
        model = profiles.get(data.get(key))
        if model is None:
            out.fail(f"pricing.json: {key} must name one of the priced inference profiles")
            return
        if model.get("lifecycle") != "Active":
            out.fail(f"pricing.json: {key} must be an Active model, not {model.get('lifecycle')!r}")
        chosen[key] = model
    kb = data.get("managed_knowledge_bases", {})
    if not str(kb.get("source_url", "")).startswith("https://aws.amazon.com/bedrock/pricing"):
        out.fail("pricing.json: managed_knowledge_bases.source_url must be the Amazon Bedrock pricing page")
    if not ISO_DATE.match(str(kb.get("read_on", ""))):
        out.fail("pricing.json: managed_knowledge_bases.read_on must be YYYY-MM-DD")
    for key in ("retrieve_per_1000_requests", "storage_per_gb_month"):
        if not isinstance(kb.get(key), (int, float)) or kb[key] <= 0:
            out.fail(f"pricing.json: managed_knowledge_bases has no positive {key}")
            return
    course, comparison = chosen["course_model"], chosen["comparison_model"]
    out.counts["pricing"] = (
        f"read {source.get('read_on')}; {len(profiles)} models; course model {course['model_name']} "
        f"${course['input']:.2f}/${course['output']:.2f}, comparison model {comparison['model_name']} "
        f"${comparison['input']:.2f}/${comparison['output']:.2f} per million input/output tokens; "
        f"Retrieve ${kb['retrieve_per_1000_requests']:.2f} per 1,000 calls"
    )


def check_readme(ds: dict, out: Findings) -> None:
    readme = ds["texts"]["README.md"]
    for name in ("kestrel-company.md", "cases.json", "users.json", "approval-case.json",
                 "questions.json", "pricing.json", "check_data.py"):
        if name not in readme:
            out.fail(f"README.md does not describe {name}")
    guide = ds.get("guide")
    if guide:
        for token in guide.get("readme_must_not_mention", []):
            if re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", readme):
                out.fail("README.md names a planted defect, which learners must not see", token)


def check_against_guide(ds: dict, docs: dict, out: Findings) -> None:
    """Confirm that each defect is the one the staff guide names."""
    guide = ds["guide"]
    pair = guide["contradiction"]["documents"]
    pattern = re.compile(guide["contradiction"]["pattern"])
    amounts = {d: set(pattern.findall(doc["body"])) for d, doc in docs.items()}
    amounts = {d: a for d, a in amounts.items() if a}
    if sorted(amounts) != sorted(pair):
        out.fail("the contradictory documents differ from the staff guide",
                 f"the guide names {pair}; the pattern matches {sorted(amounts) or 'none'}")
    elif len(set().union(*amounts.values())) < 2:
        out.fail("the contradictory documents now agree", f"{pair}")
    else:
        out.names["contradiction"] = ", ".join(f"{d} says £{'/'.join(sorted(amounts[d]))}" for d in pair)
    if ds.get("_contradicted_docs") != sorted(pair):
        out.fail("the contradicted questions cite different documents from the staff guide",
                 f"{ds.get('_contradicted_docs')}")

    stale_doc = guide["out_of_date"]["document"]
    if ds.get("_stale") != [stale_doc]:
        out.fail("the out-of-date document differs from the staff guide", f"{ds.get('_stale')}")
    else:
        doc = docs[stale_doc]
        out.names["stale"] = f"{stale_doc}, last reviewed {doc['last_reviewed']}, status {doc['status']}"

    duplicate = guide["duplicate"]["case_id"]
    positions = ds.get("_repeated", {})
    if list(positions) != [duplicate]:
        out.fail("the repeated case id differs from the staff guide", f"{list(positions)}")
    else:
        found = positions[duplicate]
        out.names["repeated"] = f"{duplicate} at record positions {found[0]} and {found[1]}"

    malformed = guide["malformed"]
    invalid = ds.get("_invalid", {})
    if list(invalid) != [malformed["case_id"]]:
        out.fail("the record that breaks the contract differs from the staff guide", f"{invalid}")
    elif invalid[malformed["case_id"]] != sorted(malformed["reasons"]):
        out.fail("the malformed record breaks the contract for different reasons from the staff guide",
                 f"{invalid[malformed['case_id']]}")
    else:
        out.names["contract"] = f"{malformed['case_id']}: " + "; ".join(sorted(malformed["reasons"]))

    injected = guide["injected"]["case_id"]
    if ds.get("_injected") != [injected]:
        out.fail("the case note that addresses an assistant differs from the staff guide",
                 f"{ds.get('_injected')}")
    else:
        out.names["injected"] = f"{injected}, in a note written by the customer"

    expected_scope = guide["out_of_scope"]["question_ids"]
    if ds.get("_out_of_scope") != expected_scope:
        out.fail("the out-of-scope questions differ from the staff guide", f"{ds.get('_out_of_scope')}")
    else:
        questions = {q["question_id"]: q for q in ds["questions.json"]["questions"]}
        out.names["out_of_scope"] = ", ".join(
            f"{qid} asks for {questions[qid]['case_id']}" for qid in expected_scope
        )


def check_approval_oracle(ds: dict, out: Findings) -> None:
    """Confirm that the staff guide's Day 9 outcome follows from the data file."""
    oracle = ds["guide"].get("approval")
    data = ds["approval-case.json"]
    if not oracle or oracle.get("approval_id") != data.get("approval_id"):
        out.fail("the staff guide has no Day 9 outcome for the approval case")
        return
    states = {s["state"]: s for s in data.get("decision_states", [])}
    outcome = oracle["expected_outcome"]
    sequence = oracle["expected_sequence"]
    for name in [*outcome.values(), *sequence]:
        if name not in states:
            out.fail("the staff guide's Day 9 outcome names an undefined state", name)
            return
    if sequence[:1] != [data.get("initial_state")]:
        out.fail("the staff guide's Day 9 sequence doesn't start at the initial state", f"{sequence[:1]}")
    for current, following in zip(sequence, sequence[1:]):
        if following not in states[current]["next_states"]:
            out.fail("the staff guide's Day 9 sequence makes a transition the decision states don't allow",
                     f"{current} to {following}")
    first, after = outcome["with_available_evidence"], outcome["after_supplementary_evidence"]
    if first not in sequence or after not in sequence[sequence.index(first) + 1:]:
        out.fail("the staff guide's Day 9 sequence doesn't pass through both expected outcomes in order",
                 f"{first}, then {after}")
    if states[sequence[-1]]["next_states"]:
        out.fail("the staff guide's Day 9 sequence doesn't end in a final state", sequence[-1])
    missing = data.get("evidence_missing", [])
    if first == "more_evidence_requested" and not missing:
        out.fail("the Day 9 outcome asks for more evidence, but the approval case has none missing")
    if first != "more_evidence_requested" and missing:
        out.fail("the approval case has missing evidence, but the Day 9 outcome doesn't ask for it", first)
    out.names["approval"] = (
        f"{len(missing)} evidence items missing; expected outcome {first}, then {after}; "
        f"sequence {' > '.join(sequence)}"
    )


def check_synthetic(ds: dict, out: Findings) -> None:
    """Screen every data file for real-looking contact details and credentials."""
    texts = dict(ds["texts"])
    texts.update({f"documents/{k}": v for k, v in ds["documents"].items()})
    for name, text in texts.items():
        for match in PHONE.finditer(text):
            digits = re.sub(r"\D", "", match.group(0))
            if not ALLOWED_PHONE.match(digits):
                out.fail(f"{name}: phone number {match.group(0)!r} is outside 01632 960000 to 960999")
        for match in EMAIL.finditer(text):
            if match.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
                out.fail(f"{name}: email address on {match.group(1)!r}")
        for match in UK_POSTCODE.finditer(text):
            out.fail(f"{name}: text that looks like a UK postcode: {match.group(0)!r}")
        for match in re.finditer(r"\bKT-\d+\b", text):
            if not POSTCODE_AREA.match(match.group(0)):
                out.fail(f"{name}: area {match.group(0)!r} is outside KT-01 to KT-09")
        for match in URL_HOST.finditer(text):
            host = match.group(1).lower()
            if not (host.endswith("kestrel.example") or host in ALLOWED_URL_HOSTS):
                out.fail(f"{name}: link to {host!r}")
        for pattern, label in ((AWS_ACCOUNT_ID, "a 12-digit number"), (ACCESS_KEY, "an access key"),
                               (ARN, "an ARN")):
            if pattern.search(text):
                out.fail(f"{name}: contains {label}")


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def run(ds: dict) -> Findings:
    ds = dict(ds)  # the checks record intermediate results on this copy
    out = Findings()
    docs = check_documents(ds, out)
    cases = check_cases(ds, out)
    users = check_users(ds, cases, out)
    check_approval(ds, cases, users, docs, out)
    check_questions(ds, docs, cases, users, out)
    check_pricing(ds, out)
    check_readme(ds, out)
    check_synthetic(ds, out)
    if ds.get("guide"):
        check_against_guide(ds, docs, out)
        check_approval_oracle(ds, out)
    return out


DEFECT_LINES = (
    ("Records that break the case contract", "contract"),
    ("Case ids that appear twice", "repeated"),
    ("Documents that are superseded and past the freshness limit", "stale"),
    ("Cases with a note that addresses an assistant", "injected"),
    ("Questions whose supporting documents disagree", "contradicted"),
    ("Questions about a case outside the asker's scope", "out_of_scope"),
)
NAMED_LINES = (
    ("Contradictory documents", "contradiction"),
    ("Out-of-date document", "stale"),
    ("Duplicate case record", "repeated"),
    ("Malformed case record", "contract"),
    ("Injected instruction", "injected"),
    ("Requests outside the user's scope", "out_of_scope"),
    ("Approval case", "approval"),
)


def report(out: Findings, staff: bool, guide_present: bool) -> None:
    print("Kestrel dataset check")
    print(f"  Reference date: {REFERENCE_DATE}; documents older than {MAX_DOCUMENT_AGE_DAYS} days are out of date.")
    for label, key in (("Documents", "documents"), ("Cases", "cases"), ("Questions", "questions"),
                       ("Approval case", "approval"), ("Prices", "pricing")):
        print(f"  {label}: {out.counts.get(key, 'not checked')}")
    print("Realistic defects, counted:")
    for label, key in DEFECT_LINES:
        print(f"  {label}: {out.counts.get(key, 'not checked')}")
    if staff:
        print("Planted defects, named (staff only):")
        for label, key in NAMED_LINES:
            print(f"  {label}: {out.names.get(key, 'MISSING')}")
    elif guide_present:
        print("  The staff guide is present, and each defect was checked against it. Use --staff to name them.")
    else:
        print("  The staff guide isn't in this folder, so the check confirmed the counts only.")
    if out.problems:
        print(f"FAIL: {len(out.problems)} problem(s)")
        for message, detail in out.problems:
            print(f"  - {message}" + (f": {detail}" if staff and detail else ""))
        if not staff and any(detail for _, detail in out.problems):
            print("  Staff can run the check with --staff for the details.")
    else:
        print("PASS: every file matches its schema, and the dataset contains the defects that the labs expect.")


def self_test(ds: dict) -> bool:
    """Remove each defect in a copy of the dataset and confirm the check fails."""
    guide = ds["guide"]

    def doc_name(doc_id: str) -> str:
        return next(n for n in ds["documents"] if n.startswith(doc_id.replace("_", "-") + "-"))

    def records(d):
        return d["cases.json"]["cases"]

    first, second = guide["contradiction"]["documents"]
    pattern = re.compile(guide["contradiction"]["pattern"])
    stale = guide["out_of_date"]["document"]
    duplicate = guide["duplicate"]["case_id"]
    malformed = guide["malformed"]["case_id"]
    injected = guide["injected"]["case_id"]
    scope_question = guide["out_of_scope"]["question_ids"][0]

    def remove_contradiction(d):
        amount = pattern.search(d["documents"][doc_name(first)]).group(1)
        name = doc_name(second)
        d["documents"][name] = pattern.sub(
            lambda m: m.group(0).replace(m.group(1), amount), d["documents"][name]
        )

    def make_stale_current(d):
        name = doc_name(stale)
        d["documents"][name] = re.sub(r"Last reviewed: \S+", "Last reviewed: 2026-06-01", d["documents"][name])

    def mark_stale_current(d):
        name = doc_name(stale)
        d["documents"][name] = d["documents"][name].replace("Status: superseded", "Status: current")

    def remove_duplicate(d):
        positions = [i for i, r in enumerate(records(d)) if r["case_id"] == duplicate]
        del records(d)[positions[-1]]

    def repair_malformed(d):
        for r in records(d):
            if r["case_id"] == malformed:
                r["owner_team"] = "technical_support"
                r["opened_at"] = r["history"][0]["at"]

    def repair_malformed_date_only(d):
        for r in records(d):
            if r["case_id"] == malformed:
                r["opened_at"] = r["history"][0]["at"]

    def remove_injection(d):
        for r in records(d):
            if r["case_id"] == injected:
                r["history"] = [h for h in r["history"] if not INJECTION.search(h["note"])]

    def bring_into_scope(d):
        users = {u["role"]: u for u in d["users.json"]["users"]}
        own = next(c["case_id"] for c in records(d) if c["customer_id"] == users["customer"]["customer_id"])
        for item in d["questions.json"]["questions"]:
            if item["question_id"] == scope_question:
                item["case_id"] = own

    def answer_no_evidence(d):
        name = doc_name("kd_02")
        d["documents"][name] += "\nStudents get 10 per cent off every plan.\n"

    def name_defect_in_readme(d):
        d["texts"]["README.md"] += f"\nThe duplicate record is {duplicate}.\n"

    def put_oracle_back(d):
        d["approval-case.json"]["expected_outcome"] = dict(d["guide"]["approval"]["expected_outcome"])

    def empty_missing_evidence(d):
        d["approval-case.json"]["evidence_missing"] = []
        d["approval-case.json"]["supplementary_evidence"] = []

    def break_oracle_sequence(d):
        d["guide"]["approval"]["expected_sequence"] = ["submitted", "approved", "applied"]

    def add_real_phone(d):
        name = doc_name("kd_01")
        d["documents"][name] = d["documents"][name].replace("01632 960100", "020 7946 0100", 1)

    mutations = [
        ("contradiction removed", remove_contradiction),
        ("out-of-date document given a current review date", make_stale_current),
        ("out-of-date document marked current", mark_stale_current),
        ("duplicate record removed", remove_duplicate),
        ("malformed record repaired", repair_malformed),
        ("malformed record half repaired (date only)", repair_malformed_date_only),
        ("injected instruction removed", remove_injection),
        ("out-of-scope request brought into scope", bring_into_scope),
        ("no-evidence question made answerable", answer_no_evidence),
        ("a planted defect named in README.md", name_defect_in_readme),
        ("Day 9 outcome put back in approval-case.json", put_oracle_back),
        ("approval case left with no missing evidence", empty_missing_evidence),
        ("Day 9 sequence skips the review", break_oracle_sequence),
        ("a phone number outside the drama range added", add_real_phone),
    ]
    baseline = run(ds)
    ok = not baseline.problems
    print("Self-test: the unmodified dataset " + ("passes." if ok else "FAILS, so the self-test is void."))
    for label, mutate in mutations:
        trial = copy.deepcopy(ds)
        mutate(trial)
        found = run(trial)
        caught = bool(found.problems)
        ok = ok and caught
        first_problem = found.problems[0] if caught else None
        shown = (f"{first_problem[0]}" + (f": {first_problem[1]}" if first_problem[1] else "")) if caught \
            else "no problem reported"
        print(f"  {'caught ' if caught else 'MISSED '} {label}: {shown}")
    print("Self-test " + ("passed: every removed defect makes the check fail." if ok else "FAILED."))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", type=Path, default=DATA,
                        help="the dataset folder to check (default: the folder that holds this script)")
    parser.add_argument("--staff", action="store_true",
                        help=f"name each planted defect; needs the staff-only {GUIDE_NAME}")
    parser.add_argument("--self-test", action="store_true",
                        help=f"remove each planted defect in memory and confirm that the check fails; "
                             f"needs the staff-only {GUIDE_NAME}")
    args = parser.parse_args()
    try:
        ds = load(args.data)
    except (OSError, ValueError) as error:
        print(f"FAIL: cannot read the dataset in {args.data}: {error}")
        return 1
    if (args.staff or args.self_test) and not ds["guide"]:
        print(f"FAIL: --staff and --self-test need {GUIDE_NAME}, which is for staff only "
              "and isn't in this folder.")
        return 1
    if args.self_test:
        return 0 if self_test(ds) else 1
    out = run(ds)
    report(out, staff=args.staff, guide_present=bool(ds["guide"]))
    return 1 if out.problems else 0


if __name__ == "__main__":
    sys.exit(main())
