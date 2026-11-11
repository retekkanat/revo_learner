# Week 1 Friday review: instructor's guide

Use this instructor guide with `week1-gate-rubric.md`, which describes the Friday review to learners and contains the record form. The learner package and site exclude this guide.

The review is an unassessed discussion of progress. Record what each learner has done and agree what they should study next. Keep the personal records outside the repository and the course sites.

## Prepare before Friday

1. Read `week1-gate-rubric.md` and this guide.
2. Prepare one private record for each learner from the review record form. Keep your Day 1 diagnostic notes to hand so you can review the subjects each learner needed help with.
3. Rehearse the demonstration of the complete Support Assistant v1 on the course account, following the Day 5 instructor guide. Before you rehearse, run the staff preflight from the repository root with `uv run tools/check_workbook.py --week 1 --live --timeout 1800`, or at least the reference's live smoke test, `reference/tests/live_smoke.py`, so that you know the course account reaches the course model. Both make real calls to Amazon Bedrock and incur charges.
4. Review the available exercises: Exercises 1, 2 and 3 from Day 3; Exercise 4 and Exercise 5, part one, from Day 4; and Exercise 5, part two, from Day 5. Each exercise starts from a supplied version of the assistant, and the exercise package guide, `README.md`, explains how a learner checks each one.
5. For each day, note the study material that you'll suggest: the day's learner handbook and its review questions, the day's Skill Builder course, and the exam guide's task statements that the day's instructor guide lists.

## Friday timetable

| Time | What happens |
| --- | --- |
| 14:05 to 14:35 | You demonstrate the complete Support Assistant v1 to the class in Block 3. The Day 5 instructor guide gives the script. |
| 15:15 to 16:15 | Five-minute reviews for up to twelve learners. The class studies the second half of AWS Partner: Agentic AI Technical Foundations while you see each learner in turn. With fewer learners, the class keeps studying until 16:15. |
| 16:15 to 16:25 | You start the teardown of the week's demonstration resources, set the weekend reading and hand off to Week 2. |
| 16:25 to 16:40 | The Day 5 knowledge check. Each learner tells you their Day 5 result, and you add it to their record. |
| 16:40 to 16:45 | You show the empty inventory of the course account and close the week. |

## Run one review in five minutes

1. **Minute 0 to 1: knowledge checks.** Ask for the number of correct answers on each of Days 1 to 4, and record them. If a learner didn't keep notes for a day, leave that day blank.
2. **Minute 1 to 2: exercises.** Ask which exercises the learner did and how far they got, and record each one as done, started or not started. Record the learner's own account of their progress. Look at saved results if they offer to show them.
3. **Minute 2 to 4: what to study next.** Agree one or two specific items with the learner, and record them. The next section explains how to choose them.
4. **Minute 4 to 5: the account for Week 2.** Ask whether the learner can sign in to the AWS account that they're arranging through their employer or a personal account. If they can't, record when they expect it, so that you can follow it up before Week 2.

Complete the record after the learner leaves, then call the next learner.

## Choose what to study next

Base the suggestion on the knowledge check results, your diagnostic notes and the subjects that the learner says they found hardest. Name the material and agree when the learner will study it.

- The day with the fewest correct answers is usually the place to start. Suggest that day's handbook section on the subject of the missed questions, its review questions and the exam guide's task statements for the day.
- A learner who hasn't finished the three introductory courses should agree when they'll finish them. The courses need about an hour and a half beyond Week 1's self-study blocks, so the weekend after Day 5 is the usual time.
- A learner who did no exercise should choose one to do in Week 2. Suggest the Week 1 exercise on the subject that they found hardest. Each exercise starts from a supplied version, so it doesn't depend on the earlier ones.
- A learner who did the exercises and answered most questions correctly can read ahead for Day 6, which configures and compares retrieval, or study the exam guide's task statements for the subjects that Week 2 teaches.

## If the demonstration can't reach the model

If a model call returns `AccessDeniedException` and the message names AWS Marketplace actions, ask the account owner to check the model's Marketplace agreement and the permissions needed to subscribe. Record the error code. Teach from the recorded runs in `live-verification.md` while access is restored, and tell the class that these are recorded results.

If the client waits and retries during the demonstration, the account's request quota is throttling the calls. Explain it to the class as the throttling and retry behaviour that Day 2 teaches.

## After the reviews

Keep every record outside the repository and the course sites. Before Week 2, follow up each learner whose AWS account isn't ready. You can't arrange or change a learner's access yourself, so point the learner to the course's account requirement and to their account owner. Learners can complete an exercise's functions and run its check without an account, but the workbook cells that call AWS need the learner's own account from Week 2. Week 2's exercises start from supplied versions of the assistant, so a learner who did no Week 1 exercise can still do them.
