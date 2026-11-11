# Exercise readiness record: Exercise 4

The course author tested these cells as Lab 4 of the lab-led Week 1 in the authoring account on 31 October 2026, and this record summarises those runs. On 2 November 2026, the lab package became optional exercises, each with a supplied version of the assistant; the cells and the code of this exercise are those that ran on 31 October. On 2 November the offline suites passed, and the exercise's check passed on the version where the exercise is complete. The complete staff workbook, which runs these cells against `reference/`, then passed the live check on 2 November 2026, from 21:22 to 22:02; the [live verification record](../../live-verification.md#current-week-1-verification) describes that run, and this record keeps the detailed results of 31 October. Both runs used version 3 of the example learner policy in the authoring account. They don't show the results under version 4 or under the policies of an account that a learner arranges. The account number is replaced with `<account-id>`. The quality report's figures are what you produce in Exercise 1.11, so this record does not give them.

- Lab ID / title: Exercise 4, the data contract and the quality report (Exercise 1.11), on the subject of Day 4; formerly Lab 4.
- Tested date and reviewer role: 31 October 2026, the course author, in the course's authoring account.
- Source revision / dependency versions: the Week 1 lab package of 31 October 2026; `boto3` 1.43.123 and `pydantic` 2.14.2 from `uv.lock`; Python 3.13.5.
- AWS Region, model and inference profile: Europe (London), `eu-west-2`, from `AWS_DEFAULT_REGION`. Exercise 4 calls no model.
- Tested identity class / role policy revision: an IAM user under the authoring policy, version 3, which matched version 3 of the example learner policy.
- Environment prerequisites: the version supplied in `starter/exercise-4/`; `FDE_OWNER` exported; the dataset in `data/` and the fixtures in `fixtures/contract-tests/`.
- Clean setup duration: creating the bucket and the on-demand table took under 30 seconds.
- Exercise duration: planning the fixtures and the dataset takes under a second; the first ingestion run took about 40 seconds and the second, which wrote nothing, a few seconds.
- Cleanup duration: the teardown, the last cell of Exercise 5, part two, or `python -m support_assistant teardown --yes`, removes the table and the emptied bucket, after the knowledge base.
- Measured charges and pricing date: S3 and DynamoDB requests and storage of well under one megabyte for under an hour; no per-request charge appears in the run's records. No model call.
- Known limitations: the bucket name takes six random letters from `work/state.json`; deleting that file gives a new bucket name on the next run.

| Check | Evidence / result | Remaining defect and owner |
| --- | --- | --- |
| Clean setup with learner-equivalent permissions | `ensure_bucket()` and `ensure_table()` created a private, tagged bucket and an on-demand, tagged table. | None. |
| Successful run | The first run wrote to all four zones and the table, and the manifest's document checksums matched their source files when the Exercise 4 check recomputed them. | None. |
| Invalid input / schema failure | The fixtures produced every kind of rejection once, each with its rule: a missing required field, a value outside the allowed set, a timestamp that is not ISO 8601, a field outside the contract, a conflicting duplicate, an unsupported file type, an audience outside the allowed set and a missing review date. | None. |
| Denied operation / wrong identity | Not exercised in Exercise 4; the role that Exercise 5 creates can read only `curated/`. | None. |
| Timeout / retry / duplicate request | The second run wrote nothing in any zone or in the table and produced the same manifest. Every wait has a limit. | None. |
| Data access and prompt injection | Ingestion copies case notes as data and never interprets them; the contract marks the personal fields. | None. |
| Sensitive data checks in logs and traces | The rejected zone holds each rejected record with its reasons; the quality report names identifiers and rules, not personal values. | None. |
| Request limits and practical stop procedure | One run makes about 150 S3 calls and a few dozen DynamoDB writes. The input dataset determines the number of writes, and polling operations have time limits. | None. |
| Repeat the exercise after a failure | `python -m support_assistant build` recreated the bucket, the table and the ingestion in one command after a full teardown. | None. |
| Deleted and remaining resources | The teardown deleted the table and the bucket with every object; the inventory listed no bucket, table or tagged resource of the exercise's in either allowed Region. | None. |

Readiness decision: ready for the recorded exercise activities.

Artefacts needed to reproduce the evidence: the Exercise 4 cells of `week1-workbook.ipynb`, `ingest.py` and `schemas.py` in `starter/exercise-4/support_assistant/`, `fixtures/contract-tests/`, `data-contract-template.md` and `starter/checks/check_exercise_4.py`. The check passed against the run's records. With no records folder, it fails on the version supplied for Exercise 4 and passes on the version supplied for Exercise 5, part one, in which Exercises 1 to 4 are complete; `reference/tests/test_starters.py` tests both.
