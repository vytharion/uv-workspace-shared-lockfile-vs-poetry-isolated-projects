#!/usr/bin/env python3
"""Quantify the cost of propagating a shared-library refactor across each setup.

A breaking change to `shared_lib.greet` (added `salutation`) has to reach
the consuming app in both trees. The uv workspace shares one lockfile,
so a single `uv sync --all-packages` re-resolves both members and the
consumer picks up the new signature with no lockfile edits of its own.
Each Poetry project owns its own lockfile, so the same refactor forces
a version bump in the library plus an independent `poetry lock` + install
inside every consumer.

The pure accounting lives here so we can unit-test the shape of the
propagation plan without shelling out to `uv` or `poetry`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class UpdatePlan:
    setup: str
    files_touched: tuple[str, ...]
    commands: tuple[str, ...]
    lockfiles_resolved: tuple[str, ...]
    version_bumps: tuple[str, ...] = ()

    @property
    def cost(self) -> int:
        return (
            len(self.files_touched)
            + len(self.commands)
            + len(self.lockfiles_resolved)
            + len(self.version_bumps)
        )


def uv_workspace_plan() -> UpdatePlan:
    return UpdatePlan(
        setup="uv workspace",
        files_touched=(
            "sample/packages/shared_lib/src/shared_lib/greetings.py",
            "sample/packages/app/src/app/main.py",
        ),
        commands=("uv sync --all-packages",),
        lockfiles_resolved=("sample/uv.lock",),
        version_bumps=(),
    )


def poetry_isolated_plan() -> UpdatePlan:
    return UpdatePlan(
        setup="poetry isolated",
        files_touched=(
            "poetry-sample/packages/shared_lib/src/shared_lib/greetings.py",
            "poetry-sample/packages/shared_lib/pyproject.toml",
            "poetry-sample/packages/app/src/app/main.py",
            "poetry-sample/packages/app/pyproject.toml",
        ),
        commands=(
            "poetry lock  # inside packages/shared_lib",
            "poetry install  # inside packages/shared_lib",
            "poetry lock  # inside packages/app",
            "poetry install  # inside packages/app",
        ),
        lockfiles_resolved=(
            "poetry-sample/packages/shared_lib/poetry.lock",
            "poetry-sample/packages/app/poetry.lock",
        ),
        version_bumps=("shared_lib 0.1.0 -> 0.2.0",),
    )


def _bulleted(header: str, items: tuple[str, ...], marker: str) -> list[str]:
    lines = [f"  {header} ({len(items)}):"]
    for item in items:
        lines.append(f"    {marker} {item}")
    return lines


def format_plan(plan: UpdatePlan) -> str:
    lines = [f"{plan.setup}: cost={plan.cost}"]
    lines.extend(_bulleted("files touched", plan.files_touched, "-"))
    lines.extend(_bulleted("commands to run", plan.commands, "$"))
    lines.extend(_bulleted("lockfiles re-resolved", plan.lockfiles_resolved, "*"))
    if plan.version_bumps:
        lines.extend(_bulleted("version bumps", plan.version_bumps, "!"))
    return "\n".join(lines)


def compare_plans(uv_plan: UpdatePlan, poetry_plan: UpdatePlan) -> str:
    delta = poetry_plan.cost - uv_plan.cost
    return (
        f"cost delta: poetry={poetry_plan.cost} vs uv={uv_plan.cost} "
        f"(+{delta} steps for the isolated setup)"
    )


def plans_as_json(uv_plan: UpdatePlan, poetry_plan: UpdatePlan) -> str:
    payload = {
        "uv_workspace": asdict(uv_plan) | {"cost": uv_plan.cost},
        "poetry_isolated": asdict(poetry_plan) | {"cost": poetry_plan.cost},
        "delta": poetry_plan.cost - uv_plan.cost,
    }
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--out",
        type=Path,
        help="also write the report to this file",
    )
    args = parser.parse_args(argv)

    uv_plan = uv_workspace_plan()
    poetry_plan = poetry_isolated_plan()

    if args.json:
        text = plans_as_json(uv_plan, poetry_plan)
    else:
        text = "\n\n".join(
            [format_plan(uv_plan), format_plan(poetry_plan), compare_plans(uv_plan, poetry_plan)]
        )

    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
