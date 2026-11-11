# Exercise readiness record: Exercise 1

The course author tested these cells as Lab 1 of the lab-led Week 1 in the authoring account on 31 October 2026, and this record summarises those runs. On 2 November 2026, the lab package became optional exercises, each with a supplied version of the assistant; the cells and the code of this exercise are those that ran on 31 October. On 2 November the offline suites passed, and the exercise's check passed on the version where the exercise is complete. The complete staff workbook, which runs these cells against `reference/`, then passed the live check on 2 November 2026, from 21:22 to 22:02; the [live verification record](../../live-verification.md#current-week-1-verification) describes that run, and this record keeps the detailed results of 31 October. Both runs used version 3 of the example learner policy in the authoring account. They don't show the results under version 4 or under the policies of an account that a learner arranges. On 5 November 2026, the Exercise 1 instructions and its check changed, so that a learner's account may allow the Ireland request; no live run has used the changed cells or check. The account number is replaced with `<account-id>`.

- Lab ID / title: Exercise 1, account checks (Exercises 1.1 to 1.3, Extensions 1E.1 and 1E.2), on the subject of Day 1; formerly Lab 1.
- Tested date and reviewer role: 31 October 2026, the course author, in the course's authoring account.
- Source revision / dependency versions: the Week 1 lab package of 31 October 2026; AWS CLI 2.39.3; Python 3.13.5; uv 0.11.29; `boto3` 1.43.123 from `uv.lock`.
- AWS Region, model and inference profile: Europe (London), `eu-west-2`, from `AWS_DEFAULT_REGION`. Exercise 1 calls no model; it lists the Anthropic models and finds the course model.
- Tested identity class / role policy revision: an IAM user under the authoring policy, version 3, whose statements matched version 3 of the example learner policy.
- Environment prerequisites: the laptop setup in the pre-work pack; `AWS_DEFAULT_REGION=eu-west-2` and `FDE_OWNER` exported; `uv sync` in the lab folder.
- Clean setup duration: about one minute for `uv sync` with a warm cache.
- Exercise duration: the Exercise 1 cells ran in about one minute, of which the wrong-Region failure case took about 35 seconds.
- Cleanup duration: the cells delete both buckets; the tag listings showed them gone within a few seconds in both Regions.
- Measured charges and pricing date: no per-request charge; two empty S3 buckets existed for under a minute each. No model call.
- Known limitations: the authoring identity is an IAM user, so its record shows `user`; a learner who uses IAM Identity Center sees `assumed-role` and a session name.

| Check | Evidence / result | Remaining defect and owner |
| --- | --- | --- |
| Clean setup with learner-equivalent permissions | The Setup cell and every Exercise 1 cell ran under a policy that matched version 3 of the example learner policy. | None. |
| Successful run | The identity record holds the principal kind and name, `<account-id>`, the alias or "no alias", the Region and the CLI version; the London listing includes the course model. | None. |
| Invalid input / schema failure | `describe_identity()` refuses text that is not an ARN. | None. |
| Denied operation / wrong identity | Listing guardrails in Europe (Ireland) returned `AccessDeniedException` because no identity-based policy allows it there; the budget call was refused by an explicit deny; the policy simulation returned `implicitDeny` for Ireland and `allowed` for London. | None. |
| Timeout / retry / duplicate request | Not applicable; the tag listing is polled with a three-minute limit. | None. |
| Data access and prompt injection | Not applicable to Exercise 1. | None. |
| Sensitive data checks in logs and traces | Every CLI command, output and error is redacted before it is shown or written; the check found no account number or key in the evidence. | None. |
| Request limits and practical stop procedure | Not applicable; each cell makes one to four CLI calls. | None. |
| Repeat the exercise after a failure | The failure case created a bucket in N. Virginia without `--region`, showed that a London-only listing misses it, found it and removed it. | None. |
| Deleted and remaining resources | The teardown record shows empty listings in `eu-west-2` and `us-east-1`. | None. |

Readiness decision: ready for the recorded exercise activities.

Artefacts needed to reproduce the evidence: the Exercise 1 cells of `week1-workbook.ipynb`, `starter/support_assistant/config.py`, `starter/checks/check_exercise_1.py`, and an account with the example learner policy. The check passed against the run's records. With no records folder, it fails on the version supplied for Exercise 1 and passes on the version supplied for Exercise 2, in which Exercise 1 is complete; `reference/tests/test_starters.py` tests both.
