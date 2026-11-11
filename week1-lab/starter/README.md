# Week 1 supplied versions of the assistant

This folder holds the versions of the `support_assistant` package that the Week 1 exercises start from, the check for each exercise and the offline tests. Each exercise names the functions you complete, and a `TODO Exercise 1.n` comment marks each one in the code.

| Folder | Exercise that starts from it | Already complete | What you complete |
| --- | --- | --- | --- |
| `support_assistant/` | 1 | Nothing | `describe_identity()` in `config.py` (Exercise 1.1) |
| `exercise-2/support_assistant/` | 2 | Exercise 1 | `result_from_response()` (1.4), `validate_structured()` (1.5), `should_interrupt()` and `stream_outcome()` (1.6), `should_retry()` and `backoff_delay()` (1.7) in `bedrock.py` |
| `exercise-3/support_assistant/` | 3 | Exercises 1 and 2 | `DRAFT_REPLY_SPEC` and `Dispatcher.dispatch()` (1.8, 1.9 and 1.10) and `approve_draft()` (1.9) in `tools.py`, and `check_limits()` (1.9) in `loop.py` |
| `exercise-4/support_assistant/` | 4 | Exercises 1 to 3 | `validate_case()` and `put_case_if_changed()` (1.11) in `ingest.py` |
| `exercise-5-part-1/support_assistant/` | 5, part one | Exercises 1 to 4 | `hit_at()` (1.12) in `retrieval.py` |
| `exercise-5-part-2/support_assistant/` | 5, part two | Exercises 1 to 5, part one | `render_template()` (1.15), `REVISED_PROMPT` (1.16) and `regression_problems()` (1.17) in `prompts.py`, and `SupportAssistant.ask()` (1.16) in `assistant.py` |

Each version also contains `TODO` comments for later exercises. You only need to complete the functions named in your chosen exercise.

The modules `ledger.py`, `schemas.py` and `__main__.py` are complete in every version. Read them to see how they work with your functions. In `retrieval.py`, `check_citations()` is complete in every version: it checks that an answer cites at least one document, that each cited document was among the passages supplied and that the manifest lists it.

## Check an exercise

Run each command from the lab folder. The `--directory` argument selects the version to test. For example, to check Exercise 3:

```bash
uv run --directory starter/exercise-3 python -m pytest ../checks/check_exercise_3.py
```

To check Exercise 1, select `starter/`:

```bash
uv run --directory starter python -m pytest checks/check_exercise_1.py
```

Each check tests only the functions needed for its exercise. It fails until you complete those functions. When `KESTREL_EVIDENCE` names your records folder, it also reads the records that the workbook saved. `checks/prompt_regression.py` is the prompt regression test of Exercise 5, part two; the lab folder's `README.md` describes how to run it.

Run the offline tests of the supplied code with:

```bash
uv run --directory starter python -m pytest -q
```

Every command runs from the lab folder (`week1-lab` in the package you receive, or `week1/labs` in the course repository) and makes no AWS call.
