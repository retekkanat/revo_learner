"""Check the supplied version of the assistant for each exercise.

Each exercise starts from a supplied version: the reference as it stands at the
end of the exercise before it. `make_starters.py` writes those versions from the
reference and the full starter. These tests check that the written versions are
up to date, and that each exercise's check fails on the version supplied for it
and passes once that exercise is complete. They catch an exercise that depends
on a later one, and a check that a later exercise's stub would break. They run
without evidence files or AWS access.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from make_starters import (
    LABS,
    REFERENCE,
    STARTER,
    exercise_folders,
    expected,
    step_exercises,
    stubs,
    version_of,
)

CHECKS = LABS / "starter" / "checks"
FOLDERS = exercise_folders()


def supplied(folder: str) -> Path:
    """Return the folder that holds the version supplied for an exercise."""
    return LABS / "starter" if folder == FOLDERS[0] else LABS / "starter" / folder


def completed(folder: str) -> Path:
    """Return the folder that holds a version with this exercise complete."""
    index = FOLDERS.index(folder)
    return supplied(FOLDERS[index + 1]) if index + 1 < len(FOLDERS) else LABS / "reference"


def run_check(folder: str, package: Path) -> subprocess.CompletedProcess:
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"KESTREL_EVIDENCE", "PYTHONPATH", "PYTHONSAFEPATH"}}
    where = subprocess.run([sys.executable, "-c", "import support_assistant; print(support_assistant.__file__)"],
                           cwd=package, env=environment, capture_output=True, text=True, timeout=60)
    assert Path(where.stdout.strip()).resolve().is_relative_to(package.resolve()), where.stdout + where.stderr
    script = CHECKS / f"check_{folder.replace('-', '_')}.py"
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(script)],
                          cwd=package, env=environment, capture_output=True, text=True, timeout=600)


def test_the_workbook_defines_six_exercises_and_every_stub_names_one_of_its_steps():
    assert FOLDERS == ["exercise-1", "exercise-2", "exercise-3", "exercise-4", "exercise-5-part-1",
                       "exercise-5-part-2"]
    steps = step_exercises()
    named = {exercise for path in STARTER.glob("*.py")
             for *_, exercise in stubs(path.read_text(encoding="utf-8"), steps)}
    assert named == set(FOLDERS)


def test_the_supplied_versions_are_up_to_date():
    files = expected()
    for path, text in files.items():
        assert path.is_file(), f"{path.relative_to(LABS)} is missing; run make_starters.py"
        assert path.read_text(encoding="utf-8") == text, f"{path.relative_to(LABS)} is out of date; run make_starters.py"
    for folder in FOLDERS[1:]:
        written = {path for path in (supplied(folder) / "support_assistant").glob("*.py")}
        assert written == {path for path in files if path.parent == supplied(folder) / "support_assistant"}


def test_completing_every_exercise_gives_the_reference():
    steps = step_exercises()
    for path in sorted(STARTER.glob("*.py")):
        reference = (REFERENCE / path.name).read_text(encoding="utf-8")
        result = version_of(path.name, path.read_text(encoding="utf-8"), reference, set(FOLDERS), steps)
        if path.name == "__init__.py":
            result = result.replace('CHECKPOINT = "starter"', 'CHECKPOINT = "reference"')
        assert result == reference, f"{path.name}: a difference from the reference names no exercise"


@pytest.mark.parametrize("folder", FOLDERS)
def test_the_check_fails_on_the_supplied_version(folder):
    result = run_check(folder, supplied(folder))
    assert result.returncode != 0, f"the {folder} check passes before the exercise is done"


@pytest.mark.parametrize("folder", FOLDERS)
def test_the_check_passes_once_the_exercise_is_complete(folder):
    result = run_check(folder, completed(folder))
    assert result.returncode == 0, (f"the {folder} check fails against {completed(folder).relative_to(LABS)}:\n"
                                    + result.stdout[-4000:] + result.stderr[-2000:])
