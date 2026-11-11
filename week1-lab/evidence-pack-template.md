# Week 1 exercise record

Use this optional record to prepare for the Friday review. Exercise 1.3 copies it to `work/evidence/<your initials>/INDEX.md`. Write a few sentences for each exercise you complete. At the review, discuss those exercises and what you need to study next with your instructor.

Keep account identifiers and credentials out of this record. Use `<account-id>` in place of the account number, including within ARNs. Don't paste access keys, session tokens or the output of `aws configure list`.

- Learner initials: [write here]

## Exercise 1: Account checks

1. Identity record. Name the account alias, or write "no alias" if the account has none. Then name the role or user, say whether the identity is an assumed role or an IAM user, and give the Region. The machine record is `day1-identity.json`.

   [write here]

2. The Ireland request. Say whether your account allowed or refused the guardrail listing in Ireland. Quote the example learner policy's `aws:RequestedRegion` condition, and explain in your own words why that policy refuses the request. If your account's result was different, say so. The machine record is `day1-calls.json`.

   [write here]

3. Budget and teardown. Say when the budget's recipients receive an alert and why an alert doesn't stop spending. Then say what you created, where you listed it, and what the empty listing in both allowed Regions shows. The machine record is `day1-teardown.json`.

   [write here]

## Exercise 2: The Bedrock client

1. Model choice. Give the model identifier from `config.py` and explain why the course uses the EU inference profile.

   [write here]

2. The ledger. Point to the rows for the first call, the rejected answer, the interrupted stream, the access denial, the throttle and its retry, and the timeout. Explain why the interrupted stream's cost is unknown rather than zero.

   [write here]

## Exercise 3: The two tools and the refusals

1. Draft approval. Show that the case history didn't change until the supervisor approved the draft. The machine record is `day3-loop.json`.

   [write here]

2. The refusals. For the unknown tool, the injected instruction and the repeated action, name the rule that the dispatcher recorded, and explain why rewording the request didn't change the decision. The machine record is `day3-refusals.json`.

   [write here]

## Exercise 4: The data contract and the quality report

1. The data contract. Point to your completed copy of `data-contract-template.md` and give its version.

   [write here]

2. The quality report. Name each rejected record's rule, the duplicates and the documents that failed the freshness check, and show that the second run wrote nothing.

   [write here]

## Exercise 5, part one: The knowledge base and the retrieval comparison

1. The comparison. Give both retrievers' hit rates in the top five and at rank one, and one question where they disagreed. The machine record is `day4-retrieval-comparison.json`.

   [write here]

2. A cited answer. For one answer, check one citation against the manifest: the document exists, its checksum matches, and the passage says what the answer claims.

   [write here]

## Exercise 5, part two: Prompt versions and a regression test

1. Version 2. Say what you changed from version 1 and why, naming the parts of the prompt you changed.

   [write here]

2. The comparison. Give the cited answers, the questions that no document answers but received an answer, and the requests outside the caller's scope for both versions. Name one question whose answer changed. The machine records are `day5-prompt-version-1.json` and `day5-prompt-version-2.json`.

   [write here]

3. The regression test. Say what the test compares, what made it fail in the failure case, and the tolerance you would set from your measurements.

   [write here]

## What to study next

Note the subjects you found hardest this week, for the Friday review.

[write here]
