"""Command-line entry for Support Assistant v1.

Run from the folder of the package you are using, for example:

    uv run --directory starter python -m support_assistant build
    uv run --directory starter python -m support_assistant ask "How do I make a complaint?" --user user_customer_01
    uv run --directory starter python -m support_assistant run-prompt --version 2
    uv run --directory starter python -m support_assistant teardown --yes

`build` creates or reuses the Exercise 4 bucket and table, ingests the dataset
under the contract and creates or reuses the managed knowledge base, in one
command, so that any exercise or a later week can rebuild everything from the
same code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import boto3

from . import config
from .assistant import SupportAssistant, inventory, teardown
from .bedrock import BedrockClient
from .ingest import dataset_sources, ensure_bucket, ensure_table, ingest, load_manifest, plan_ingestion, \
    quality_report, save_lab4_outputs
from .ledger import EvidenceFolder, Ledger
from .retrieval import KeywordBaseline, Retriever, compare_retrievers, ensure_data_source, ensure_kb_role, \
    ensure_knowledge_base, load_corpus, sync
from .tools import DynamoCaseStore, LocalCaseStore, load_users


def build() -> dict:
    """Create or reuse the Exercise 4 and Exercise 5 resources and load new or changed dataset records."""
    started = time.perf_counter()
    names = config.resource_names()
    region = config.region()
    s3 = boto3.client("s3", region_name=region)
    dynamodb = boto3.client("dynamodb", region_name=region)
    ensure_bucket(s3, names.bucket)
    ensure_table(dynamodb, names.table)
    cases, documents = dataset_sources()
    plan = plan_ingestion(cases, documents, config.reference_date())
    manifest, writes = ingest(plan, s3=s3, dynamodb=dynamodb, bucket=names.bucket, table=names.table)
    report = quality_report(plan, writes)
    account = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    role_arn = ensure_kb_role(boto3.client("iam"), account, names.role, names.bucket)
    agent = boto3.client("bedrock-agent", region_name=region)
    kb_id = ensure_knowledge_base(agent, names.knowledge_base, role_arn)
    ds_id = ensure_data_source(agent, kb_id, names.data_source, names.bucket, account)
    report["ingestion_job"] = sync(agent, kb_id, ds_id)
    save_lab4_outputs(manifest, report)
    state = config.load_state()
    state.update(knowledge_base_id=kb_id, data_source_id=ds_id, bucket=names.bucket, table=names.table)
    config.save_state(state)
    return {"knowledge_base_id": kb_id, "data_source_id": ds_id, "writes": writes,
            "ingestion_job": report["ingestion_job"], "seconds": round(time.perf_counter() - started, 1)}


def prompt_version(version: str | None):
    """Return a numbered version of the assistant's prompt from Prompt Management, or None for the code's prompt."""
    if version is None:
        return None
    from .prompts import find_prompt, load_version

    agent = boto3.client("bedrock-agent", region_name=config.region())
    prompt_id = find_prompt(agent, config.resource_names().prompt)
    if prompt_id is None:
        raise config.ConfigurationError("No prompt is saved yet. Run Exercise 1.15 first.")
    return load_version(agent, prompt_id, version)


def make_assistant(local_cases: bool = False, version: str | None = None) -> SupportAssistant:
    """Assemble v1 from the resources that `build` recorded in `work/state.json`."""
    state = config.load_state()
    if "knowledge_base_id" not in state:
        raise config.ConfigurationError("No knowledge base is recorded. Run `python -m support_assistant build` first.")
    ledger = Ledger()
    runtime = boto3.client("bedrock-agent-runtime", region_name=config.region())
    store = LocalCaseStore() if local_cases else DynamoCaseStore(state["table"])
    return SupportAssistant(client=BedrockClient(ledger=ledger), retriever=Retriever(state["knowledge_base_id"], runtime, ledger),
                            case_store=store, manifest=load_manifest(), prompt=prompt_version(version))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m support_assistant", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="Create or reuse the bucket, table and managed knowledge base, and ingest.")
    ask = commands.add_parser("ask", help="Ask one question as one of the four users.")
    ask.add_argument("question", help="The question, in quotation marks.")
    ask.add_argument("--user", default="user_customer_01", help="A user_id from data/users.json.")
    ask.add_argument("--prompt-version", help="A numbered prompt version from Prompt Management; "
                                              "without it, the prompt written in the code.")
    run = commands.add_parser("run-prompt", help="Run one prompt version on the question set and the injection "
                                                 "cases, and save the record.")
    run.add_argument("--version", required=True, help="The numbered prompt version to run, such as 2.")
    commands.add_parser("compare", help="Measure the keyword baseline against the knowledge base.")
    commands.add_parser("inventory", help="List resources with this learner's course tags or names.")
    down = commands.add_parser("teardown", help="Remove the prompt, knowledge base, data source, table, bucket "
                                                "and role.")
    down.add_argument("--yes", action="store_true", help="Confirm that you want to delete the resources.")
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            result = build()
        elif args.command == "ask":
            users = load_users()
            if args.user not in users:
                parser.error(f"--user must be one of {', '.join(users)}")
            result = make_assistant(version=args.prompt_version).ask(args.question, users[args.user]).model_dump()
        elif args.command == "run-prompt":
            from .prompts import run_version

            assistant = make_assistant(version=args.version)
            questions = json.loads((config.DATA_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
            record = run_version(assistant, assistant.prompt, questions, load_users(), ledger=assistant.client.ledger)
            path = EvidenceFolder().write(f"day5-prompt-version-{args.version}.json", record)
            result = {"summary": record["summary"], "saved_to": str(path.relative_to(config.LABS_DIR))}
        elif args.command == "compare":
            state = config.load_state()
            questions = json.loads((config.DATA_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
            runtime = boto3.client("bedrock-agent-runtime", region_name=config.region())
            result = compare_retrievers(questions, KeywordBaseline(load_corpus()),
                                        Retriever(state["knowledge_base_id"], runtime))
            EvidenceFolder().write("day4-retrieval-comparison.json", result)
        elif args.command == "inventory":
            result = inventory()
        else:
            if not args.yes:
                parser.error("teardown deletes resources; add --yes to confirm")
            result = {"removed": teardown(), "left": inventory()}
    except config.ConfigurationError as error:
        print(f"Configuration problem: {error}", file=sys.stderr)
        return 2
    print(config.redact(json.dumps(result, indent=2, ensure_ascii=False, default=str)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
