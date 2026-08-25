"""Unit-test the pure logic of the step-6 refactor cost planner.

The plans themselves are hard-coded snapshots that describe what a human
would have to do to propagate a breaking change in `shared_lib.greet`
under each dependency manager. We are not measuring wall-clock time here
— that already lives in the step-5 bench harness — we are counting the
files, commands, lockfiles, and version bumps each setup demands.
"""
from __future__ import annotations

import json

from refactor_cost import (
    UpdatePlan,
    compare_plans,
    format_plan,
    plans_as_json,
    poetry_isolated_plan,
    uv_workspace_plan,
)


def test_uv_plan_touches_exactly_one_lockfile() -> None:
    plan = uv_workspace_plan()
    assert plan.lockfiles_resolved == ("sample/uv.lock",)


def test_uv_plan_needs_no_version_bump() -> None:
    plan = uv_workspace_plan()
    assert plan.version_bumps == ()


def test_uv_plan_runs_a_single_sync_command() -> None:
    plan = uv_workspace_plan()
    assert len(plan.commands) == 1
    assert plan.commands[0].startswith("uv sync")


def test_poetry_plan_touches_both_project_lockfiles() -> None:
    plan = poetry_isolated_plan()
    assert plan.lockfiles_resolved == (
        "poetry-sample/packages/shared_lib/poetry.lock",
        "poetry-sample/packages/app/poetry.lock",
    )


def test_poetry_plan_requires_a_version_bump_of_shared_lib() -> None:
    plan = poetry_isolated_plan()
    assert len(plan.version_bumps) == 1
    assert "shared_lib" in plan.version_bumps[0]
    assert "0.1.0" in plan.version_bumps[0]
    assert "0.2.0" in plan.version_bumps[0]


def test_poetry_plan_touches_both_pyproject_files() -> None:
    plan = poetry_isolated_plan()
    pyprojects = [f for f in plan.files_touched if f.endswith("pyproject.toml")]
    assert len(pyprojects) == 2


def test_poetry_plan_costs_strictly_more_than_uv_plan() -> None:
    uv_plan = uv_workspace_plan()
    poetry_plan = poetry_isolated_plan()
    assert poetry_plan.cost > uv_plan.cost


def test_update_plan_cost_sums_all_dimensions() -> None:
    plan = UpdatePlan(
        setup="fake",
        files_touched=("a", "b"),
        commands=("run",),
        lockfiles_resolved=("lock",),
        version_bumps=("bump",),
    )
    assert plan.cost == 5


def test_format_plan_contains_setup_label_and_cost() -> None:
    text = format_plan(uv_workspace_plan())
    assert "uv workspace" in text
    assert "cost=" in text


def test_format_plan_omits_version_bump_section_when_none() -> None:
    text = format_plan(uv_workspace_plan())
    assert "version bumps" not in text


def test_format_plan_includes_version_bump_section_for_poetry() -> None:
    text = format_plan(poetry_isolated_plan())
    assert "version bumps" in text
    assert "shared_lib" in text


def test_compare_plans_reports_positive_delta_for_poetry() -> None:
    uv_plan = uv_workspace_plan()
    poetry_plan = poetry_isolated_plan()
    summary = compare_plans(uv_plan, poetry_plan)
    assert "poetry=" in summary
    assert "uv=" in summary
    assert "+" in summary


def test_plans_as_json_is_parseable_and_carries_delta() -> None:
    uv_plan = uv_workspace_plan()
    poetry_plan = poetry_isolated_plan()
    payload = json.loads(plans_as_json(uv_plan, poetry_plan))
    assert payload["uv_workspace"]["cost"] == uv_plan.cost
    assert payload["poetry_isolated"]["cost"] == poetry_plan.cost
    assert payload["delta"] == poetry_plan.cost - uv_plan.cost
