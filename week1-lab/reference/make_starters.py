"""Write the supplied version of the assistant for each Week 1 exercise.

Exercise 1 starts from `starter/support_assistant/`, in which every exercise's
functions are still to be completed. The version supplied for each later
exercise is the reference as it stands at the end of the exercise before it:
the functions of the earlier exercises are complete, and those of that exercise
and the later ones still carry their `TODO Exercise` comments.

The script writes those versions to `starter/<exercise>/support_assistant/`
from two sources, the complete `reference/support_assistant/` and the full
starter, so the copies can't drift from either. It compares the two sources
line by line. Each difference lies inside a definition whose `TODO Exercise
1.n` comment names a workbook step, and the workbook's `# Exercise` headings say
which exercise each step belongs to. A version takes the reference's side of
every difference that belongs to an earlier exercise.

Run it from the lab folder after you change either source:

    uv run --directory reference python make_starters.py

`tests/test_starters.py` fails when a written version is out of date.
"""

from __future__ import annotations

import ast
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
STARTER = LABS / "starter" / "support_assistant"
REFERENCE = LABS / "reference" / "support_assistant"
WORKBOOK = LABS / "week1-workbook.ipynb"
EXERCISE_HEADING = re.compile(r"^# Exercise (\d+)(?:, part (one|two))?:")
STEP_HEADING = re.compile(r"^#{2,4} Exercise (\d+\.\d+):")
TODO = re.compile(r"TODO Exercises? (\d+\.\d+(?:(?:, | and )\d+\.\d+)*)")
CHECKPOINT_LINE = 'CHECKPOINT = "starter"'


def exercise_folders() -> list[str]:
    """Return the exercises in workbook order, as folder names such as `exercise-5-part-1`."""
    return list(dict.fromkeys(step_exercises().values()))


def step_exercises() -> dict[str, str]:
    """Return {workbook step: exercise folder} from the workbook's headings."""
    notebook = json.loads(WORKBOOK.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    current = None
    for cell in notebook["cells"]:
        if cell["cell_type"] != "markdown":
            continue
        for line in "".join(cell["source"]).splitlines():
            if heading := EXERCISE_HEADING.match(line):
                number, part = heading.groups()
                current = f"exercise-{number}" + ({"one": "-part-1", "two": "-part-2"}[part] if part else "")
            elif (step := STEP_HEADING.match(line)) and current:
                found[step.group(1)] = current
    return found


def definitions(tree: ast.Module) -> dict[str, ast.AST]:
    """Return the module's functions, methods and settings by dotted name."""
    found: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found[f"{node.name}.{item.name}"] = item
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    found[target.id] = node
    return found


def stubs(source: str, steps: dict[str, str]) -> list[tuple[str, int, int, str]]:
    """Return (name, first line, last line, exercise folder) for each stub in one starter module.

    A setting's stub includes the comment lines above it, where its TODO is written.
    """
    lines = source.splitlines()
    order = list(dict.fromkeys(steps.values()))
    found = []
    for name, node in definitions(ast.parse(source)).items():
        first = min([node.lineno] + [decorator.lineno for decorator in getattr(node, "decorator_list", [])])
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            while first > 1 and lines[first - 2].lstrip().startswith("#"):
                first -= 1
        marker = TODO.search("\n".join(lines[first - 1:node.end_lineno]))
        if marker:
            named = re.findall(r"\d+\.\d+", marker.group(1))
            unknown = [step for step in named if step not in steps]
            if unknown:
                raise ValueError(f"{name} names workbook steps that the workbook does not have: {unknown}")
            exercise = max((steps[step] for step in named), key=order.index)
            found.append((name, first, node.end_lineno, exercise))
    return found


def differences(starter: str, reference: str, module: str, steps: dict[str, str]) -> list[tuple]:
    """Return (starter lines, reference lines, exercise) for each difference between the two sources."""
    ours, theirs = starter.splitlines(keepends=True), reference.splitlines(keepends=True)
    owner: dict[int, str] = {}
    for _, first, last, exercise in stubs(starter, steps):
        for number in range(first, last + 1):
            owner[number] = exercise
    found = []
    matcher = difflib.SequenceMatcher(None, ours, theirs, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Lines are numbered from 1; an insertion has no starter lines, so it takes its neighbours' owner.
        lines = range(i1 + 1, i2 + 1) if i2 > i1 else (i1, i1 + 1)
        owners = {owner[number] for number in lines if number in owner}
        if len(owners) > 1:
            raise ValueError(f"{module}: one difference spans exercises {sorted(owners)}")
        if not owners:
            if module != "__init__.py":
                raise ValueError(f"{module}: the starter differs from the reference at line {i1 + 1}, "
                                 "outside any definition that a TODO names")
            continue
        found.append((i1, i2, j1, j2, owners.pop()))
    return found


def version_of(module: str, starter: str, reference: str, completed: set[str], steps: dict[str, str]) -> str:
    """Return the starter module with the reference's side of every completed exercise's difference."""
    ours, theirs = starter.splitlines(keepends=True), reference.splitlines(keepends=True)
    for i1, i2, j1, j2, exercise in sorted(differences(starter, reference, module, steps), reverse=True):
        if exercise in completed:
            ours[i1:i2] = theirs[j1:j2]
    return "".join(ours)


def expected() -> dict[Path, str]:
    """Return {path: text} for every module of every supplied version after Exercise 1."""
    steps = step_exercises()
    order = exercise_folders()
    files: dict[Path, str] = {}
    for index, folder in enumerate(order[1:], start=1):
        completed = set(order[:index])
        for path in sorted(STARTER.glob("*.py")):
            text = version_of(path.name, path.read_text(encoding="utf-8"),
                              (REFERENCE / path.name).read_text(encoding="utf-8"), completed, steps)
            if path.name == "__init__.py":
                if CHECKPOINT_LINE not in text:
                    raise ValueError(f"the starter's __init__.py has no line {CHECKPOINT_LINE!r}")
                text = text.replace(CHECKPOINT_LINE, f'CHECKPOINT = "starter/{folder}"')
            ast.parse(text)
            files[LABS / "starter" / folder / "support_assistant" / path.name] = text
    return files


def main() -> int:
    files = expected()
    folders = {path.parents[1] for path in files}
    for folder in sorted(folders):
        if (folder / "support_assistant").exists():
            shutil.rmtree(folder / "support_assistant")
    for path, text in sorted(files.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for folder in sorted(folders):
        print(f"wrote {folder.relative_to(LABS)}/support_assistant/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
