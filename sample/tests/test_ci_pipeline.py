"""Unit-test the pure logic of the step-7 CI pipeline model.

The two GitHub Actions workflows in `.github/workflows/` cannot run
inside pytest (no runner, no network). We test only the deterministic
pieces: the per-step arithmetic on `Pipeline`, the shape of the two
built-in pipelines, and the formatters that produce the report the
article quotes.
"""
from __future__ import annotations

import json
from pathlib import Path

from ci_pipeline import (
    Pipeline,
    PipelineStep,
    compare_pipelines,
    format_pipeline,
    pipelines_as_json,
    poetry_pipeline,
    uv_pipeline,
)


CODEBASE_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = CODEBASE_ROOT / ".github" / "workflows"


def test_pipeline_step_is_frozen_and_defaults_to_non_cacheable() -> None:
    step = PipelineStep("setup-python", cold_seconds=3.0, warm_seconds=3.0)
    assert step.cacheable is False


def test_pipeline_cold_total_sums_all_step_cold_seconds() -> None:
    steps = (
        PipelineStep("a", cold_seconds=1.0, warm_seconds=0.5),
        PipelineStep("b", cold_seconds=2.5, warm_seconds=0.5),
    )
    assert Pipeline("demo", steps=steps).cold_total == 3.5


def test_pipeline_warm_total_and_cache_savings() -> None:
    steps = (
        PipelineStep("a", cold_seconds=4.0, warm_seconds=1.0, cacheable=True),
        PipelineStep("b", cold_seconds=1.0, warm_seconds=1.0),
    )
    p = Pipeline("demo", steps=steps)
    assert p.warm_total == 2.0
    assert p.cache_savings == 3.0


def test_pipeline_cacheable_steps_filters_the_marked_ones() -> None:
    steps = (
        PipelineStep("a", cold_seconds=1.0, warm_seconds=1.0),
        PipelineStep("b", cold_seconds=5.0, warm_seconds=1.0, cacheable=True),
        PipelineStep("c", cold_seconds=2.0, warm_seconds=0.5, cacheable=True),
    )
    p = Pipeline("demo", steps=steps)
    assert tuple(s.name for s in p.cacheable_steps) == ("b", "c")


def test_uv_pipeline_has_exactly_one_cacheable_install_step() -> None:
    p = uv_pipeline()
    install_steps = [s for s in p.cacheable_steps if s.name == "uv-sync"]
    assert len(install_steps) == 1


def test_uv_pipeline_warm_is_faster_than_cold() -> None:
    p = uv_pipeline()
    assert p.warm_total < p.cold_total
    assert p.cache_savings > 0


def test_poetry_pipeline_fans_out_across_both_packages() -> None:
    p = poetry_pipeline()
    install_steps = [s for s in p.cacheable_steps if s.name.startswith("poetry-install")]
    names = tuple(sorted(s.name for s in install_steps))
    assert names == ("poetry-install[app]", "poetry-install[shared_lib]")


def test_poetry_pipeline_cold_strictly_exceeds_uv_pipeline_cold() -> None:
    assert poetry_pipeline().cold_total > uv_pipeline().cold_total


def test_poetry_pipeline_warm_still_exceeds_uv_pipeline_warm() -> None:
    # Even with cache hits on both matrix legs, Poetry pays two
    # `install-poetry` bootstraps and two setup-python steps that
    # the uv workflow only pays once.
    assert poetry_pipeline().warm_total > uv_pipeline().warm_total


def test_format_pipeline_contains_totals_and_cache_count() -> None:
    text = format_pipeline(uv_pipeline())
    assert "uv workspace" in text
    assert "cold=" in text
    assert "warm=" in text
    assert "cacheable" in text


def test_compare_pipelines_reports_positive_cold_and_warm_delta() -> None:
    summary = compare_pipelines(uv_pipeline(), poetry_pipeline())
    assert "cold delta" not in summary  # phrasing check — we emit "pipeline delta"
    assert "pipeline delta" in summary
    assert "poetry cold=" in summary
    assert "uv cold=" in summary


def test_pipelines_as_json_carries_deltas_and_totals() -> None:
    uv = uv_pipeline()
    poetry = poetry_pipeline()
    payload = json.loads(pipelines_as_json(uv, poetry))
    assert payload["uv_workspace"]["cold_total"] == uv.cold_total
    assert payload["poetry_isolated"]["warm_total"] == poetry.warm_total
    assert payload["cold_delta"] == round(poetry.cold_total - uv.cold_total, 3)
    assert payload["warm_delta"] == round(poetry.warm_total - uv.warm_total, 3)


def test_uv_workflow_file_uses_single_lockfile_cache_key() -> None:
    text = (WORKFLOWS_DIR / "ci-uv.yml").read_text(encoding="utf-8")
    assert "sample/uv.lock" in text
    assert "uv sync --all-packages" in text


def test_poetry_workflow_file_fans_out_across_matrix() -> None:
    text = (WORKFLOWS_DIR / "ci-poetry.yml").read_text(encoding="utf-8")
    assert "matrix:" in text
    assert "shared_lib" in text and "app" in text
    assert "poetry install" in text
