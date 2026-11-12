# Week 1 · Day 4 demonstration

A Jupyter notebook demonstration of Day 4, *Data validation and document retrieval*, with a recap of every Day 1–3 demonstration. It runs the completed reference `support_assistant` package on the course AWS account.

## Contents

| Path | What it is |
| --- | --- |
| `week1-day4-demo.ipynb` | The demonstration notebook (98 cells, 28 of them call AWS) |
| `support_assistant/` | A copy of `Exercise packages/week1-lab/reference/support_assistant/`, unchanged |
| `data/`, `fixtures/` | The Kestrel dataset and the contract-test fixtures. The staff-only `planted-defects-assessor-guide.md` is left out on purpose, because this folder may be on the projector. |
| `policies/learner-permissions.json` | The example learner policy, which Day 1's offline IAM evaluator reads |
| `scripts/build_notebook.py` | Generates the notebook. **Edit the cells here**, then run `uv run python scripts/build_notebook.py` |
| `pyproject.toml`, `uv.lock` | The lab's environment plus `botocore[crt]`, which boto3 needs for `aws login` profiles |
| `week1-day4-demo-rehearsal.ipynb` | The full live rehearsal run of 11 November 2026 on `fde-demo` (owner `demo`), with all its outputs. Show this if the account fails in class. |
| `work/` | Created at run time: state, ledger, run log, manifest, build logs. Delete it for a clean run. |

## Requirements

| Requirement | Version | Why |
| --- | --- | --- |
| Python | 3.12 or 3.13 | `pyproject.toml` pins `>=3.12,<3.14`. uv downloads it if it's missing. |
| [uv](https://docs.astral.sh/uv/) | any recent | Recommended installer; uses `uv.lock` for exact versions |
| AWS CLI v2 | 2.27.42 or later | The notebook calls `aws` for the identity, policy, model-access and teardown cells |
| AWS access | profile with Bedrock (Claude Haiku 4.5 `AVAILABLE` in eu-west-2), S3, DynamoDB, IAM role creation and Bedrock knowledge bases | For the `%%live` cells only |

The Python libraries are declared in `pyproject.toml` (locked in `uv.lock`) and exported to `requirements.txt`: boto3, botocore with the `crt` extra, pydantic, jupyterlab, ipykernel, nbformat and nbclient.

### Install with uv (recommended)

```bash
cd demo
uv sync
```

### Install with pip

```bash
cd demo
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

After changing a dependency in `pyproject.toml`, refresh the lock and the pip file:

```bash
uv lock && uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

## Run it

```bash
cd demo
uv sync
aws login --profile fde-demo          # or aws sso login, depending on how the profile is set up
export AWS_PROFILE=fde-demo AWS_DEFAULT_REGION=eu-west-2 FDE_OWNER=<your initials>
uv run jupyter lab week1-day4-demo.ipynb
```

The notebook uses the kernel **Python (FDE Day 4 demo)**, which is this folder's `.venv`. If you open it from another Jupyter, such as Homebrew's `jupyter lab` or VS Code, and see `No module named 'boto3'`, choose that kernel under *Kernel › Change Kernel*. On a new machine, register it once:

```bash
uv run python -m ipykernel install --user --name fde-day4-demo --display-name "Python (FDE Day 4 demo)"
```

If you don't export them, the setup cell defaults to `fde-demo`, `eu-west-2` and the owner `demo`. The owner value names and tags every resource (`fde-<owner>-kestrel-…`).

Cells that start with `%%live` call AWS. If the credentials check fails, they print a skip notice and **Run All still completes**: every offline cell (the policy evaluator, the cost and quota maths, the stubbed retries, the dispatcher refusals, the scripted limits, the contract, the fixture plan, chunking, BM25 and the citation check) runs on the laptop.

## Mapping to the Day 4 guide

| Time | Notebook section |
| --- | --- |
| 09:00 catch-up | 4 intro, or Parts 1 to 3 as a recap |
| 10:45 demonstration, part one | 4.1 contract → 4.2 fixture plan → 4.3 **start build-1** (background process) |
| 10:55–11:35 teaching | The "While the build runs" cells: RAG, managed vs customer-managed, chunking, keyword baseline |
| 11:35 demonstration, part two | 4.4 build output → 4.5 stored data → 4.6 build-2 + kd_06 trace → 4.7 compare → 4.8 ask → 4.9 the five-second fault |
| 13:15 Block 3 | 4.10 kd_07 cited-answer check, plus the Glue DQ and services table |
| End of day | Part 5: cost, inventory. **Keep the resources for Day 5**, and tear down after Day 5. |

The MCQ keys for each day are in collapsed `<details>` blocks.

## Rules kept from the guide

- The dataset's rejected records and duplicates appear as **counts only**. Nothing under `rejected/` is opened. The fixtures are shown in full.
- All output goes through `config.redact()`, so no account number or access key ID is printed.
- Rehearse the day before: run the whole notebook, save its outputs as the fallback if the account is unavailable in class, then tear down and rebuild.
