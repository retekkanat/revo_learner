# Week 1 reference package

This instructor-only folder contains the completed `support_assistant` package for all five Week 1 exercises. The staff workbook runs each exercise against this package. Learners use the supplied versions in `starter/`.

| Exercise | Modules | What the completed code does |
| --- | --- | --- |
| 1 | `config.py` | Reads the Region and the owner from the environment, holds the model constant and the limits, runs the AWS CLI with redaction, and splits a caller ARN. |
| 2 | `bedrock.py`, `ledger.py`, `schemas.py` | Sends Converse and ConverseStream requests with SDK retries off, validates structured answers, retries the configured temporary errors, and writes one ledger row per attempt with a cost from `pricing.json`. |
| 3 | `tools.py`, `loop.py` | Defines `lookup_case` and `draft_reply`, dispatches requests through the allowlist, schema, repeat and scope checks, holds drafts for a supervisor's approval, and bounds the loop by model calls and a deadline. |
| 4 | `ingest.py` | Applies contract version 1.0, writes the four zones and the case table idempotently, and keeps the manifest and the quality report. |
| 5, part one | `retrieval.py`, `assistant.py` | Builds the managed knowledge base, compares it with a keyword baseline, answers from retrieved passages and matches every citation to a passage it supplied and to the manifest. |
| 5, part two | `prompts.py`, `assistant.py`, `__main__.py` | Keeps the assistant's prompt as a template with versions in Amazon Bedrock Prompt Management, routes each question with one prompt version on both routes, runs a version on the question set and the Day 3 injection cases, and compares two versions. The command line adds `build`, `run-prompt` and `teardown`. |

Support Assistant v1 answers from the passages it retrieves, with no filter for the caller's access to documents, no relevance threshold and no register of documents that disagree. Week 2 adds these checks on Day 6. Its completed implementation and tests are in `week2/labs/reference/`.

## Tests

Run the offline suite and the live smoke test from the lab folder:

```bash
uv run --directory reference python -m pytest -q
uv run --directory reference python -m tests.live_smoke
```

The first command runs the tests offline. The second makes one paid Converse call through the course inference profile and prints the request identifier, usage and cost.

- `tests/test_reference.py` tests the completed code exercise by exercise, with scripted responses, botocore's Stubber and in-memory stores in place of AWS.
- `tests/test_prompts.py` tests the template, the versions in Prompt Management against an in-memory stand-in, the injection runs and the regression rule.
- `tests/test_starters.py` checks the supplied versions in `starter/`. It fails when a version is out of date. For each exercise, it checks that the exercise's check fails on the version supplied for it and passes on the version where the exercise is complete, which catches an exercise that depends on a later one.

## The supplied versions

`make_starters.py` writes the code supplied for Exercises 2–5 to `starter/exercise-<n>/support_assistant/`. It combines the completed package in this folder with the unfinished functions in `starter/support_assistant/`. Each supplied version includes completed functions for earlier exercises and unfinished functions for its own and later exercises.

The script compares the two sources line by line. A `TODO Exercise 1.n` comment must associate each difference with a workbook step. The workbook's `# Exercise` headings identify which exercise contains that step.

After you change this package or the full starter, run the script from the lab folder and then the suite:

```bash
uv run --directory reference python make_starters.py
uv run --directory reference python -m pytest -q
```

For a function that learners complete, update both the completed function and its starter definition. Keep their differences inside the definition marked by its `TODO` comment. For supplied code, update the reference package; the script copies it to the starters. The script stops and identifies any difference it cannot associate with an exercise.

## Prompt versions

`prompts.LOCAL_PROMPT` is version 1: the system prompt of `loop.py` and the answer instructions of `assistant.py`, arranged as one template with the variables `{{passages}}` and `{{question}}`. `prompts.REVISED_PROMPT` is the reference's version 2. The live run of 2 November 2026, recorded in `../readiness/exercise-5-part-2.md`, gives the measures of both versions and of the failure case.
