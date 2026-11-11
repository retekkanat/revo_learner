# Exercise readiness record: Exercise 3

The course author tested these cells as Lab 3 of the lab-led Week 1 in the authoring account on 31 October 2026, and this record summarises those runs. On 2 November 2026, the lab package became optional exercises, each with a supplied version of the assistant; the cells and the code of this exercise are those that ran on 31 October. On 2 November the offline suites passed, and the exercise's check passed on the version where the exercise is complete. The complete staff workbook, which runs these cells against `reference/`, then passed the live check on 2 November 2026, from 21:22 to 22:02; the [live verification record](../../live-verification.md#current-week-1-verification) describes that run, and this record keeps the detailed results of 31 October. Both runs used version 3 of the example learner policy in the authoring account. They don't show the results under version 4 or under the policies of an account that a learner arranges. The account number is replaced with `<account-id>`.

- Lab ID / title: Exercise 3, the two tools and the refusals (Exercises 1.8 to 1.10, Extensions 1E.5 and 1E.6), on the subject of Day 3; formerly Lab 3.
- Tested date and reviewer role: 31 October 2026, the course author, in the course's authoring account.
- Source revision / dependency versions: the Week 1 lab package of 31 October 2026; `boto3` 1.43.123 and `pydantic` 2.14.2 from `uv.lock`; Python 3.13.5.
- AWS Region, model and inference profile: Europe (London), `eu-west-2`; the course model through `eu.anthropic.claude-haiku-4-5-20251001-v1:0`.
- Tested identity class / role policy revision: an IAM user under the authoring policy, version 3, which matched version 3 of the example learner policy.
- Environment prerequisites: the version supplied in `starter/exercise-3/`.
- Clean setup duration: no extra setup.
- Exercise duration: the Exercise 3 cells took about 30 seconds of call time, most of it waiting out throttles from the account's quota of 10 requests a minute.
- Cleanup duration: nothing to remove; drafts and approved notes stay in `work/`.
- Measured charges and pricing date: 16 successful model calls and 30 throttled attempts, about 0.03 USD at the prices in `data/pricing.json` read on 31 October 2026.
- Known limitations: the draft request must be about an open case. On a closed case the course model reasonably declined to propose a reply, which is why the workbook drafts on an open case.

| Check | Evidence / result | Remaining defect and owner |
| --- | --- | --- |
| Clean setup with learner-equivalent permissions | The loop needs only the model call. | None. |
| Successful run | A question about a case ran `lookup_case` once and answered after two model calls; the `toolUse` and `toolResult` blocks shared one identifier. A draft request on an open case looked the case up, proposed a draft, and ended `awaiting_approval`; the case history changed only after the supervisor approved it. | None. |
| Invalid input / schema failure | An input with the wrong field is refused by the `input_schema` rule. | None. |
| Denied operation / wrong identity | A constructed `issue_refund` request was refused by `allowlist`; a request for another case was refused by `scope`; only a supervisor may approve a draft. | None. |
| Timeout / retry / duplicate request | A repeated `lookup_case` with the same input was refused by `repeated_action`; the time limit is checked before every model call. | None. |
| Data access and prompt injection | The workbook's search found the one case note that addresses an assistant. On that case the course model looked the case up and proposed a draft about the customer's problem that followed none of the note's demands, and the draft waited for approval. Four reworded requests for another case each ended in the same `scope` refusal from the dispatcher. | None. |
| Sensitive data checks in logs and traces | Every decision line holds an input digest, never the input; no draft text reaches the log. | None. |
| Request limits and practical stop procedure | The iteration limit stops the loop at `MAX_MODEL_CALLS`; the rewording runs used a limit of three model calls. | None. |
| Repeat the exercise after a failure | The application rejects a second approval or rejection of an already decided draft. A new run can create a new proposal. | None. |
| Deleted and remaining resources | Nothing is created in AWS. | None. |

Readiness decision: ready for the recorded exercise activities.

Artefacts needed to reproduce the evidence: the Exercise 3 cells of `week1-workbook.ipynb`, `tools.py` and `loop.py` in `starter/exercise-3/support_assistant/`, and `starter/checks/check_exercise_3.py`. The check passed against the run's records. With no records folder, it fails on the version supplied for Exercise 3 and passes on the version supplied for Exercise 4, in which Exercises 1 to 3 are complete; `reference/tests/test_starters.py` tests both. Exercise 5, part two, runs the same injection cases with each prompt version.
