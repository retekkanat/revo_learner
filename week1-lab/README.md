# Week 1 exercise package

The five Week 1 exercises use Support Assistant v1, a support-case assistant for Kestrel Telecom, a fictional broadband provider. Each exercise covers one day's teaching and asks you to complete part of the assistant. Exercise 5 has two parts. This package contains the workbook, the code for each exercise, the Kestrel dataset and the tests.

The exercises are optional, and the course expects one exercise a week. Each exercise starts from supplied code with the earlier exercises complete, so you can choose any exercise without completing the others first. During Week 1, the instructor demonstrates each exercise on the course account.

## What you need

You need the tools that the pre-work installs: Python 3.12 or 3.13, uv, and AWS CLI version 2.27.42 or later. The AWS CLI and boto3 read your credentials from their configured sources, such as your AWS profile.

To run the workbook cells that call AWS, you also need an AWS account or role that meets the course's [account requirement](../../planning/account-requirement.md). Arrange it through your employer or with a personal account by the start of Week 2. Until then, you can complete an exercise's functions and run its check, which tests your code without calling AWS.

The course doesn't require particular permissions policies. The two example learner policies belong to the optional [centrally managed setup](../../accounts/managed-account-setup.md), and your account owner can grant access in another way. A request that the example policy refuses can therefore succeed in your account, as the Ireland request in Exercise 1.2 can. Before you run an exercise's AWS cells, confirm with the account owner that your identity can create, use and remove what the exercise lists under [Resources, cost and teardown](#resources-cost-and-teardown), and that the account can call the course model. Keep the workbook's resource names, tags, limits and cleanup steps, so that you and the account owner can find and remove everything that an exercise creates.

## Contents

| Path | What it is |
| --- | --- |
| `week1-workbook.ipynb` | The notebook for the five exercises, with instructions and the cells that run each exercise and save its records. |
| `starter/support_assistant/` | The version of the assistant that Exercise 1 starts from. Every exercise's functions are still to be completed, and a `TODO Exercise` comment marks each one. |
| `starter/exercise-2/` to `starter/exercise-5-part-2/` | The version that each later exercise starts from, with the earlier exercises complete. |
| `starter/checks/` | The check for each exercise, `check_exercise_1.py` to `check_exercise_5_part_2.py`, and the prompt regression test of Exercise 5, part two, `prompt_regression.py`. |
| `starter/tests/` | The offline tests of the code that every version supplies complete. |
| `data/` | The Kestrel Telecom dataset; `data/README.md` describes every file. |
| `fixtures/contract-tests/` | Records built to break the Exercise 4 data contract in known ways. |
| `data-contract-template.md` | The data contract that you complete in Exercise 4 before you load anything. |
| `evidence-pack-template.md` | An optional record of the exercises you do. Use it to prepare for the Friday review. |
| `week1-gate-rubric.md` | The Friday review: what the instructor asks about and the review record. |

The instructor package also includes the completed implementation in `reference/`, the instructor's guide to the Friday review in `week1-review-assessor-guide.md`, and the authoring test records in `readiness/`. These staff materials are excluded from the learner package.

## The exercises

| Exercise | Subject | Available from | Supplied version | What you complete |
| --- | --- | --- | --- | --- |
| 1, account checks | Accounts, identity, Regions and costs (Day 1) | Day 3 | `starter/` | `describe_identity()` in `config.py` |
| 2, the client | Calling a Claude model through Amazon Bedrock (Day 2) | Day 3 | `starter/exercise-2/` | `result_from_response()`, `validate_structured()`, `should_interrupt()`, `stream_outcome()`, `should_retry()` and `backoff_delay()` in `bedrock.py` |
| 3, the two tools and the refusals | Tools and execution limits (Day 3) | Day 3 | `starter/exercise-3/` | `DRAFT_REPLY_SPEC`, `Dispatcher.dispatch()` and `approve_draft()` in `tools.py`, and `check_limits()` in `loop.py` |
| 4, the data contract and the quality report | Data validation (Day 4) | Day 4 | `starter/exercise-4/` | `validate_case()` and `put_case_if_changed()` in `ingest.py`, and your copy of the data contract |
| 5, part one, the knowledge base and the retrieval comparison | Document retrieval (Day 4) | Day 4 | `starter/exercise-5-part-1/` | `hit_at()` in `retrieval.py` |
| 5, part two, prompt versions and a regression test | Prompt design and testing (Day 5) | Day 5 | `starter/exercise-5-part-2/` | `render_template()`, `REVISED_PROMPT` and `regression_problems()` in `prompts.py`, and `SupportAssistant.ask()` in `assistant.py` |

Week 1 numbers its steps through the week, not by exercise. Exercise 1 holds steps 1.1 to 1.3, Exercise 2 steps 1.4 to 1.7, Exercise 3 steps 1.8 to 1.10, Exercise 4 step 1.11, Exercise 5, part one, step 1.12, and part two steps 1.15 to 1.17. The workbook has no steps 1.13 and 1.14.

## The supplied versions

Each supplied version is a complete `support_assistant` package. Exercise 1 starts from `starter/`, in which every exercise's functions are still to be completed. The version for each later exercise is the completed assistant as it stands at the end of the exercise before it. For example, `starter/exercise-3/` has the functions of Exercises 1 and 2 complete, and still has the `TODO Exercise` comments of Exercise 3 and the later exercises.

Work in the folder for your chosen exercise and complete the functions it names. After trying the exercise, compare your work with the completed functions in the next supplied version.

## Setup

1. Open a terminal in this folder and create the locked environment:

   ```bash
   uv sync
   ```

2. Configure your AWS profile in the same terminal. If you use IAM Identity Center with the `fde` profile, sign in when your session has expired:

   ```bash
   export AWS_PROFILE=fde
   aws sso login --profile fde
   ```

   If you sign in with an access key instead, keep it in the AWS CLI's own credentials file, and set `AWS_PROFILE=fde` and nothing else. Never put a key, a secret or a token in a file in this folder, a notebook or a message.

3. Set the Region to Europe (London) and enter your initials. The exercises use your initials in resource names and tags. The Exercise 1 failure case deliberately creates a test bucket in US East (N. Virginia); the other resources use London.

   ```bash
   export AWS_DEFAULT_REGION=eu-west-2
   export AWS_REGION="$AWS_DEFAULT_REGION"
   export FDE_OWNER=<your initials>
   ```

   On Windows PowerShell, use `$Env:AWS_PROFILE = "fde"`, `$Env:AWS_DEFAULT_REGION = "eu-west-2"`, `$Env:AWS_REGION = $Env:AWS_DEFAULT_REGION` and `$Env:FDE_OWNER = "ab"`, replacing `ab` with your initials. Set `AWS_PROFILE` only if you configured that profile. If your workspace supplies temporary credentials or uses the default profile, leave it unset. Apply these settings on the computer that runs JupyterLab, which can differ from the computer that shows its browser.

4. Confirm that the package can see both settings. The command makes no AWS call.

   ```bash
   uv run --directory starter python -c "from support_assistant import config; print(config.region(), config.owner(), config.MODEL_ID)"
   ```

5. Start JupyterLab from this folder, in the same terminal, and open `week1-workbook.ipynb`:

   ```bash
   uv run jupyter lab
   ```

## Run an exercise

1. In the workbook, restart the kernel and run the **Setup** cell.
2. Go to the exercise and run its first code cell. The cell imports the version of `support_assistant` supplied for that exercise and shows which folder it came from.
3. Complete the functions that each step names, in that version's folder. After you edit a module, restart the kernel, then run **Setup** and the exercise's first code cell again.
4. Run the exercise's cells in order. Cells tagged `live-call` call AWS.
5. Run the exercise's check, which is the last cell of the exercise.

## Check an exercise

For a notebook check without AWS access, run **Setup**, open your exercise with its first code cell, and run `run_check("exercise-1", include_evidence=False)` in a new cell, replacing the exercise name as needed. The final check in each exercise also requires the saved results of its AWS cells. A code-only pass does not establish that the live exercise passed.

Each check tests your functions without calling AWS. The workbook's check cells also set `KESTREL_EVIDENCE` to your records folder so the check can read the saved results. Run the command for your chosen exercise from the lab folder:

| Exercise | Command |
| --- | --- |
| 1 | `uv run --directory starter python -m pytest checks/check_exercise_1.py` |
| 2 | `uv run --directory starter/exercise-2 python -m pytest ../checks/check_exercise_2.py` |
| 3 | `uv run --directory starter/exercise-3 python -m pytest ../checks/check_exercise_3.py` |
| 4 | `uv run --directory starter/exercise-4 python -m pytest ../checks/check_exercise_4.py` |
| 5, part one | `uv run --directory starter/exercise-5-part-1 python -m pytest ../checks/check_exercise_5_part_1.py` |
| 5, part two | `uv run --directory starter/exercise-5-part-2 python -m pytest ../checks/check_exercise_5_part_2.py` |

A check fails until you complete its exercise's functions, and passes once they are complete. It doesn't depend on any later exercise. The offline tests of the supplied code run with `uv run --directory starter python -m pytest -q`.

The prompt regression test of Exercise 5, part two, compares two saved runs of the assistant's prompt. Run it from `starter/exercise-5-part-2/` after the workbook has saved both runs:

```bash
cd starter/exercise-5-part-2
KESTREL_EVIDENCE=../../work/evidence/<initials> KESTREL_CANDIDATE_VERSION=2 uv run python -m pytest ../checks/prompt_regression.py
```

On Windows PowerShell, use:

```powershell
cd starter/exercise-5-part-2
$Env:KESTREL_EVIDENCE = "../../work/evidence/<initials>"
$Env:KESTREL_CANDIDATE_VERSION = "2"
uv run python -m pytest ../checks/prompt_regression.py
Remove-Item Env:KESTREL_EVIDENCE, Env:KESTREL_CANDIDATE_VERSION
```

The test fails when the candidate version gives fewer cited answers than the baseline, version 1, or when the model asks for more cases outside the caller's scope. `KESTREL_BASELINE_VERSION` sets another baseline, and `KESTREL_TOLERANCE` sets how many cited answers the candidate may lose before the test fails.

## The course model

`MODEL_ID` in `config.py` specifies Claude Haiku 4.5 through the EU inference profile `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, checked on 31 October 2026. All course model calls use this constant, and the prompt that Exercise 5, part two, saves in Prompt Management stores the same identifier.

An inference profile routes requests to its configured destination Regions. The EU profile uses only European Regions, which meets Kestrel's requirement to keep its data in Europe. The cost calculations use the dated prices in `data/pricing.json`.

Before you use an Anthropic model, the account owner completes the use-case form and makes the first call, which accepts the account's AWS Marketplace agreement. That first activation needs Marketplace permissions that the example learner policy alone doesn't grant. In a personal account, you are the account owner and complete these steps yourself. Exercise 1 includes an availability check. If it doesn't report `AVAILABLE`, ask the account owner to complete the activation.

Exercise 5, part two, uses Amazon Bedrock Prompt Management to create, version, read and delete prompts in Europe (London). The example learner policy permits these actions; under other policies, check that your identity has them. Converse can run a stored prompt version through the EU inference profile, but that request cannot supply a separate system prompt or inference settings. The assistant fills the template in its own code to configure each request.

## Run the assistant from the command line

Run these commands from the lab folder. Each command selects the supplied version it needs:

| Command | What it does |
| --- | --- |
| `uv run --directory starter/exercise-5-part-2 python -m support_assistant build` | Creates or reuses the Exercise 4 bucket and table, validates and loads the dataset, and creates or reuses the knowledge base and its data source. It then syncs the knowledge base. Repeating the command with unchanged data creates no duplicate resources or records. |
| `uv run --directory starter/exercise-5-part-2 python -m support_assistant ask "<question>" --user user_customer_01` | Asks Support Assistant v1 one question as one of the four users in `data/users.json`. Add `--prompt-version 2` to use a version from Prompt Management. It needs `SupportAssistant.ask()`, which Exercise 5, part two, completes. |
| `uv run --directory starter/exercise-5-part-2 python -m support_assistant run-prompt --version 2` | Runs one prompt version on the question set and the injection cases, and saves the record `day5-prompt-version-2.json`. |
| `uv run --directory starter/exercise-5-part-2 python -m support_assistant compare` | Measures the keyword baseline against the knowledge base. |
| `uv run --directory starter python -m support_assistant inventory` | Lists resources with your course tags or names in both allowed Regions. |
| `uv run --directory starter python -m support_assistant teardown --yes` | Removes the prompt and its versions, the data source, the knowledge base, the table, the emptied bucket and the knowledge base's role, then lists what is left. |

`inventory` and `teardown` use only supplied code, so they work in every version. `build` needs the functions of Exercise 4, and `compare` needs `hit_at()` from Exercise 5, part one, so run them from `starter/exercise-5-part-2/` or from a version in which you have completed those functions.

## Resources, cost and teardown

| Exercise | What it creates | Tags | Removed |
| --- | --- | --- | --- |
| 1 | Two scratch S3 buckets, one of them on purpose in US East (N. Virginia) | `course=fde-aws`, `lab=1`, `owner=<initials>` | In the exercise |
| 2 | Nothing; model calls only | None | Not applicable |
| 3 | Nothing; model calls and local files in `work/` | None | Not applicable |
| 4 | The ingestion bucket `fde-<initials>-kestrel-<six letters>` and the on-demand DynamoDB table `fde-<initials>-kestrel-cases` | `lab=4` | By the teardown |
| 5, part one | The IAM role `fde-<initials>-kestrel-kb-role`, the managed knowledge base `fde-<initials>-kestrel-kb` and its S3 data source; it also uses the Exercise 4 bucket and table, and creates them if they don't exist | `lab=5` on the knowledge base and the role | By the teardown |
| 5, part two | The prompt `fde-<initials>-kestrel-assistant` in Prompt Management and its versions; it also uses the resources of Exercise 4 and part one, and creates them with `build` if they don't exist | `lab=5` on the prompt | By the teardown, the last cell of the exercise |

The `lab` tag holds the number of the exercise that created the resource. Keep the bucket, the table and the knowledge base between Exercise 4 and the two parts of Exercise 5 if you are going on. While idle, the managed knowledge base incurs storage charges only, and the dataset occupies well under a megabyte in the bucket and the table. The ledger records charges for model calls, `Retrieve` calls and agentic retrieval. Exercise 5, part two, runs each prompt version on the 30 questions and the 5 injection cases, which takes about 47 model calls and 30 `Retrieve` calls, four to five minutes and about 0.16 USD for each version at a quota of 10 requests a minute.

Budget alerts notify you and the account owner after billing data updates. They don't stop requests or delete resources. Run the teardown to remove the resources that would continue to incur storage charges, whichever exercise you stop after.

The teardown deletes the prompt, then the data source, and waits for that deletion to complete before it deletes the knowledge base. It then deletes the table, the bucket's objects, the bucket and the service role. Each step skips a resource that doesn't exist. Its final inventory checks course tags in both allowed Regions and lists matching resource names. The tagging API can go on listing a deleted prompt and its versions for some time after the teardown, so the inventory checks each listed prompt with Prompt Management and reports one that no longer exists under `deleted_but_still_tagged`, a separate list inside what is left. Deleting the data source can take ten minutes or more; let the command finish. Week 2 recreates the resources with `python -m support_assistant build`.

## Records

Every record goes to `work/`, which Git ignores:

- `work/calls.jsonl` is the ledger: one row for every attempt to call AWS, with its status, tokens, request identifier and cost. When usage is unknown, the cost field is empty; this doesn't mean that the attempt was free.
- `work/runlog.jsonl` is the decision log: one line for every decision about a request. Each line names the rule and a SHA-256 hash of the input. It doesn't contain the input itself.
- `work/evidence/<initials>/` is your records folder. The workbook saves the records of each exercise here. The name of each record starts with the day whose subject it belongs to, such as `day3-refusals.json` for Exercise 3 or `day5-prompt-version-2.json` for Exercise 5, part two. Exercise 4 also copies `data-contract-template.md` here as `data-contract.md`, for you to complete.

The exercise record is optional. Exercise 1 copies `evidence-pack-template.md` to `INDEX.md` in your records folder. Use its sections to record what you did and prepare for the Friday review.

Keep account numbers, access keys, secret keys, session tokens and the output of `aws configure list` out of your records. The code removes account numbers before it displays or saves output, and each check looks for account numbers and key-shaped text in your records.

## Friday review

On Friday, the instructor demonstrates the complete Support Assistant v1, then reviews the week with each learner for five minutes: the knowledge check results, the exercises done and what to study next. The review isn't an assessment. `week1-gate-rubric.md` describes it and holds the review record. Instructors use `week1-review-assessor-guide.md`, which is staff only. Review records are personal records and stay outside the repository.

## Fault guide

| What you see | Cause | What to do |
| --- | --- | --- |
| `Configuration problem: AWS_DEFAULT_REGION is not set` | A new terminal without the Region | Export `AWS_DEFAULT_REGION=eu-west-2`, then restart the kernel. |
| `You must specify a region` from the AWS CLI | The command has no configured Region | Export the variable, or pass `--region`. |
| `FDE_OWNER must hold your initials` | The variable is missing or not two to four lower-case letters | Export `FDE_OWNER`, then restart the kernel. |
| `There is no supplied version in ...` | The exercise's first code cell names a folder that doesn't exist | Check that the lab folder holds `starter/exercise-<n>/`, and that JupyterLab started in the lab folder. |
| A cell uses an earlier version of your code | The kernel kept the module it imported first | Restart the kernel, then run **Setup** and the exercise's first code cell again. |
| `The SSO session associated with this profile has expired` or `ExpiredToken` | Your sign-in has ended | Run `aws sso login --profile fde`. |
| `AccessDeniedException` on `ListGuardrails` in Ireland | The example learner policy doesn't allow this action in Ireland, and your account's policies may not either | Explain the refusal from the policy's Region condition. If your account allows the listing, record that result instead; it doesn't mean that the exercise failed. |
| `AccessDeniedException` from the resource listing in `us-east-1` | Your organisation blocks requests in US East (N. Virginia) | Ask the account owner whether the tagging API may be used there. If it may not, record the refusal; the Exercise 1 check's teardown test then fails, and its other tests still check your work. |
| `AccessDeniedException` that names AWS Marketplace actions on a model call | The account has no Marketplace agreement for the model yet | Stop and ask the account owner to activate the model; their first call, made with the Marketplace permissions, accepts the agreement. |
| `ValidationException` about on-demand throughput | The request named the base model identifier | Use `config.MODEL_ID`, the EU inference profile. |
| `NotImplementedError: TODO Exercise 1.n` | A function that the exercise asks you to complete | Complete it, restart the kernel and run **Setup** and the exercise's first code cell. |
| Many `ThrottlingException` rows with "Too many requests" | The account's quota for the model is low; the authoring account's quota was 10 requests a minute on 31 October 2026 | The client waits and retries up to `MAX_ATTEMPTS`; if runs still fail, ask the account owner to request a higher quota in Service Quotas. |
| `ReadTimeoutError` outside Exercise 1.7 | A slow response or a network problem | Run the cell again once; the client never retries a timeout by itself. |
| `The data source reports FAILED` | The connector refused its settings | Read the reason it prints; `ensure_data_source()` replaces a failed data source when you run the cell again. |
| An ingestion job is `COMPLETE` with `warnings` | The knowledge base role could not read a prefix | Read the warning; the role may read only `curated/`. |
| `TIMED_OUT` from a wait | The wait limit passed before the job finished | Poll the same job again with a longer timeout. |
| `BucketAlreadyExists` | A bucket name is taken globally | Delete `bucket_suffix` from `work/state.json` and run the cell again for a new name. |
| `No knowledge base is recorded` | A command that needs the knowledge base ran before it existed | Run Exercise 5, part one, or `python -m support_assistant build`. |
| `ResourceNotFoundException` from `Retrieve` in Exercise 5, part two | `work/state.json` records a knowledge base that a teardown removed | Delete `knowledge_base_id` from `work/state.json`, then run the cell that prepares the knowledge base again. |
| `ValueError: no value for the variable` or `uses a variable it does not declare` | A template and its variables don't match | Check the spelling of each `{{name}}` in your version against its `variables`. |
| `ValidationException` that says overriding a field during runtime isn't supported | A Converse request that names a prompt version also sent a system prompt, inference settings or tools | Send the variables only, or fill the template in code as the assistant does. |
| The prompt regression test fails | The candidate version lost cited answers, or the model asked for more cases outside the scope | Read the reported problem, revise the prompt and rerun the comparison before choosing a version to use. |
| A deleted prompt appears under `deleted_but_still_tagged` | The tagging API lists a prompt for some time after its deletion | Nothing; Prompt Management has confirmed that the prompt no longer exists. |
| A deleted bucket still appears in a tag listing | The tagging API can lag behind a deletion | The workbook polls for up to three minutes; list again before you record the teardown. |
| A bucket appears in US East (N. Virginia) | A command ran without a Region and a profile defaulted to `us-east-1` | Delete the bucket with `--region us-east-1`, then check resource listings in both allowed Regions. |

## Data and fixtures

`data/README.md` describes every file in the dataset and its schema. The dataset includes defects such as those found in support records, and the exercises ask you to find and handle them. `fixtures/contract-tests/README.md` describes the fixtures, which break one contract rule each and are never loaded into your bucket or table.

## For instructors

The instructor package also holds `reference/`, the completed package, and the staff copy of the workbook, which runs every exercise against `reference/` instead of the supplied versions. `reference/README.md` describes the reference, the tests and `reference/make_starters.py`, which writes the supplied versions from the reference and the full starter. Week 2's separate exercise package supplies its Day 6 retrieval checks.

Run the offline suites and the staff preflight from the repository root:

```bash
uv run tools/check_workbook.py --week 1
uv run tools/check_workbook.py --week 1 --live --timeout 1800
```

The live check first runs `uv run python -m tests.live_smoke` in `reference/`, then executes the staff workbook from Exercise 1 to the teardown at the end of Exercise 5, part two. It makes paid calls and creates and removes the resources of Exercises 4 and 5.

Allow a timeout of 1,800 seconds for each cell: creating the knowledge base and its data source, running two prompt versions and the teardown are the longest operations. The records in `readiness/` and `../live-verification.md` contain the measured authoring timings and costs.
