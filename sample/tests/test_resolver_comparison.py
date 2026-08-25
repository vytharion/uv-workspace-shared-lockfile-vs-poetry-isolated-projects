"""Assert the invariants that make step 4's resolver comparison meaningful.

The uv workspace lock at `sample/uv.lock` pins pytest exactly once for the
whole workspace, while the two Poetry projects under `poetry-sample/`
each carry their own `poetry.lock` and are free to disagree. Step 4
deliberately pins `pytest` to incompatible ranges in the two Poetry
projects, so this test locks in that observable outcome and will fail
loudly if a future change accidentally re-unifies the pins.
"""
from __future__ import annotations

import re
from pathlib import Path

SAMPLE_ROOT = Path(__file__).resolve().parents[1]
CODEBASE_ROOT = SAMPLE_ROOT.parent
UV_LOCK = SAMPLE_ROOT / "uv.lock"
POETRY_LOCKS = {
    "shared_lib": CODEBASE_ROOT / "poetry-sample" / "packages" / "shared_lib" / "poetry.lock",
    "app": CODEBASE_ROOT / "poetry-sample" / "packages" / "app" / "poetry.lock",
}

_PACKAGE_BLOCK = re.compile(
    r'\[\[package\]\]\s*\nname = "([^"]+)"\s*\nversion = "([^"]+)"'
)


def _pinned(lock_path: Path) -> dict[str, str]:
    text = lock_path.read_text(encoding="utf-8")
    return {name: version for name, version in _PACKAGE_BLOCK.findall(text)}


def test_uv_workspace_pins_pytest_exactly_once() -> None:
    text = UV_LOCK.read_text(encoding="utf-8")
    pytest_blocks = re.findall(
        r'\[\[package\]\]\s*\nname = "pytest"\s*\nversion = "([^"]+)"',
        text,
    )
    assert len(pytest_blocks) == 1, (
        f"expected a single pytest pin in the shared workspace lock, "
        f"got {pytest_blocks}"
    )


def test_poetry_projects_pin_different_pytest_versions() -> None:
    shared_lib_pytest = _pinned(POETRY_LOCKS["shared_lib"])["pytest"]
    app_pytest = _pinned(POETRY_LOCKS["app"])["pytest"]
    assert shared_lib_pytest != app_pytest, (
        f"expected divergent pytest pins across the two Poetry projects, "
        f"got shared_lib={shared_lib_pytest} app={app_pytest}"
    )


def test_poetry_shared_lib_stays_on_pytest_8() -> None:
    version = _pinned(POETRY_LOCKS["shared_lib"])["pytest"]
    assert version.startswith("8."), (
        f"shared_lib pyproject pins pytest>=8,<9; lock has {version}"
    )


def test_poetry_app_stays_on_pytest_9() -> None:
    version = _pinned(POETRY_LOCKS["app"])["pytest"]
    assert version.startswith("9."), (
        f"app pyproject pins pytest>=9,<10; lock has {version}"
    )
