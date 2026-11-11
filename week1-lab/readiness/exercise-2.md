# Exercise readiness record: Exercise 2

The course author tested these cells as Lab 2 of the lab-led Week 1 in the authoring account on 31 October 2026, and this record summarises those runs. On 2 November 2026, the lab package became optional exercises, each with a supplied version of the assistant; the cells and the code of this exercise are those that ran on 31 October. On 2 November the offline suites passed, and the exercise's check passed on the version where the exercise is complete. The complete staff workbook, which runs these cells against `reference/`, then passed the live check on 2 November 2026, from 21:22 to 22:02; the [live verification record](../../live-verification.md#current-week-1-verification) describes that run, and this record keeps the detailed results of 31 October. Both runs used version 3 of the example learner policy in the authoring account. They don't show the results under version 4 or under the policies of an account that a learner arranges. The account number is replaced with `<account-id>`.

- Lab ID / title: Exercise 2, the Bedrock client (Exercises 1.4 to 1.7, Extensions 1E.3 and 1E.4), on the subject of Day 2; formerly Lab 2.
- Tested date and reviewer role: 31 October 2026, the course author, in the course's authoring account.
- Source revision / dependency versions: the Week 1 lab package of 31 October 2026; `boto3` and `botocore` 1.43.123 and `pydantic` 2.14.2 from `uv.lock`; Python 3.13.5.
- AWS Region, model and inference profile: Europe (London), `eu-west-2`; Claude Haiku 4.5 through `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, whose seven destination Regions are all European AWS Regions; the model is Active.
- Tested identity class / role policy revision: an IAM user under the authoring policy, version 3, which matched version 3 of the example learner policy, including the two AWS Marketplace actions that the first call to a model needs.
- Environment prerequisites: the version supplied in `starter/exercise-2/`; the account owner has completed the Anthropic use-case form and made the first call, so that `agreementAvailability.status` reports `AVAILABLE`.
- Clean setup duration: no extra setup.
- Exercise duration: the Exercise 2 cells ran in about 25 seconds, including the ten calls of Extension 1E.4.
- Cleanup duration: nothing to remove; the ledger and the records stay in `work/`.
- Measured charges and pricing date: the first call used 25 input and 31 output tokens, with a service latency of about 500 milliseconds, and cost 0.0002 USD at the prices in `data/pricing.json` read on 31 October 2026. The Exercise 2 cells cost about 0.005 USD without the extensions; Extension 1E.4 cost about 0.022 USD.
- Known limitations: the authoring account's quota for the course model was 10 requests a minute, against an AWS default of 10,000. The client retried every throttle to success with its bounded policy, and every throttled attempt is a ledger row. An account with the same quota runs the workbook more slowly; the account owner can request a higher quota.

| Check | Evidence / result | Remaining defect and owner |
| --- | --- | --- |
| Clean setup with learner-equivalent permissions | The availability check reported `AVAILABLE` and the calls succeeded under a policy that matched version 3 of the example learner policy. | None. |
| Successful run | The first call returned text, `end_turn`, usage, latency and a request identifier, and one ledger row with its cost. The structured summary validated. The complete stream ended with `end_turn` and its usage. | None. |
| Invalid input / schema failure | A `maxTokens` of 25 cut the JSON off; the client recorded `rejected` with the stop reason `max_tokens` and did not use the answer. | None. |
| Denied operation / wrong identity | The base model identifier was refused in London with a `ValidationException` about on-demand throughput. The injected `AccessDeniedException` was recorded once and not retried. | None. |
| Timeout / retry / duplicate request | The injected `ThrottlingException` was retried once after a jittered wait; a read timeout of one second raised `ReadTimeoutError`, recorded as `timed_out` with unknown cost and not retried. Genuine throttles from the account's quota were retried to success. | None. |
| Data access and prompt injection | The case summary prompt marks the case record as data; Exercise 3 tests injection. | None. |
| Sensitive data checks in logs and traces | Ledger rows hold no prompt or answer text; error messages are redacted. | None. |
| Request limits and practical stop procedure | SDK retries are off; the client stops at `MAX_ATTEMPTS`; the interrupted stream stopped at 15 pieces and closed the stream. | None. |
| Repeat the exercise after a failure | Every cell can run again; the ledger appends rows. | None. |
| Deleted and remaining resources | Nothing is created. | None. |

Native structured output (Extension 1E.3) worked on the course model: the record validated against `CaseSummary`. The comparison model in Extension 1E.4, `eu.anthropic.claude-sonnet-4-6`, produced valid summaries at about three times the cost and twice the latency.

Readiness decision: ready for the recorded exercise activities.

Artefacts needed to reproduce the evidence: the Exercise 2 cells of `week1-workbook.ipynb`, `bedrock.py`, `ledger.py` and `schemas.py` in `starter/exercise-2/support_assistant/`, `data/pricing.json` and `starter/checks/check_exercise_2.py`. The check passed against the run's records. With no records folder, it fails on the version supplied for Exercise 2 and passes on the version supplied for Exercise 3, in which Exercises 1 and 2 are complete; `reference/tests/test_starters.py` tests both.
