"""Unit-test the step-8 decision matrix that ranks uv workspaces vs Poetry isolation.

The matrix is a pure data structure over the evidence collected in
steps 1-7. These tests pin the scoring arithmetic, the shape of the
canonical criterion set, the scenario reweightings, and the JSON /
text formatters. Nothing here shells out — the matrix must stay
deterministic so the article can quote the numbers directly.
"""
from __future__ import annotations

import json

import pytest

from decision_matrix import (
    Criterion,
    DecisionMatrix,
    Recommendation,
    Verdict,
    default_matrix,
    format_matrix,
    format_recommendation,
    hybrid_scenario,
    matrix_as_json,
    monorepo_scenario,
    multi_team_scenario,
    recommend,
    scenario_by_name,
)


def _criterion(
    name: str = "sample",
    weight: int = 2,
    verdict: Verdict = Verdict.UV_WINS,
    step: int = 5,
) -> Criterion:
    return Criterion(
        name=name,
        weight=weight,
        verdict=verdict,
        rationale=f"rationale for {name}",
        evidence_step=step,
    )


def test_criterion_rejects_weight_below_one() -> None:
    with pytest.raises(ValueError):
        _criterion(weight=0)


def test_criterion_rejects_weight_above_three() -> None:
    with pytest.raises(ValueError):
        _criterion(weight=4)


def test_criterion_rejects_out_of_range_evidence_step() -> None:
    with pytest.raises(ValueError):
        _criterion(step=99)


def test_matrix_scoring_partitions_weight_by_verdict() -> None:
    matrix = DecisionMatrix(
        name="synthetic",
        criteria=(
            _criterion("a", weight=3, verdict=Verdict.UV_WINS),
            _criterion("b", weight=2, verdict=Verdict.POETRY_WINS),
            _criterion("c", weight=1, verdict=Verdict.TIE),
        ),
    )
    assert matrix.uv_score == 3
    assert matrix.poetry_score == 2
    assert matrix.tie_weight == 1
    assert matrix.total_weight == 6


def test_matrix_criteria_for_filters_by_verdict() -> None:
    matrix = DecisionMatrix(
        name="synthetic",
        criteria=(
            _criterion("a", verdict=Verdict.UV_WINS),
            _criterion("b", verdict=Verdict.POETRY_WINS),
            _criterion("c", verdict=Verdict.UV_WINS),
        ),
    )
    picked = matrix.criteria_for(Verdict.UV_WINS)
    assert tuple(c.name for c in picked) == ("a", "c")


def test_default_matrix_has_nine_criteria() -> None:
    assert len(default_matrix().criteria) == 9


def test_default_matrix_criteria_names_are_unique() -> None:
    names = [c.name for c in default_matrix().criteria]
    assert len(names) == len(set(names))


def test_default_matrix_covers_all_three_verdicts() -> None:
    verdicts = {c.verdict for c in default_matrix().criteria}
    assert verdicts == {Verdict.UV_WINS, Verdict.POETRY_WINS, Verdict.TIE}


def test_default_matrix_leans_uv_but_stays_close() -> None:
    matrix = default_matrix()
    assert matrix.uv_score > matrix.poetry_score
    diff = matrix.uv_score - matrix.poetry_score
    assert diff <= 3  # canonical view is uv-leaning, not uv-blowout


def test_recommend_default_picks_uv_workspace() -> None:
    result = recommend(default_matrix())
    assert result.recommendation is Recommendation.USE_UV_WORKSPACE
    assert result.uv_score > result.poetry_score
    assert 0.0 <= result.margin_ratio <= 1.0


def test_recommend_ignores_tie_weight_in_scoring() -> None:
    matrix = DecisionMatrix(
        name="tie-heavy",
        criteria=(
            _criterion("a", weight=3, verdict=Verdict.UV_WINS),
            _criterion("b", weight=3, verdict=Verdict.POETRY_WINS),
            _criterion("c", weight=3, verdict=Verdict.TIE),
        ),
    )
    result = recommend(matrix)
    assert result.tie_weight == 3
    assert result.recommendation is Recommendation.EITHER_WORKS


def test_recommend_returns_either_works_when_scores_are_within_ten_percent() -> None:
    matrix = DecisionMatrix(
        name="close",
        criteria=(
            _criterion("a", weight=3, verdict=Verdict.UV_WINS),
            _criterion("b", weight=3, verdict=Verdict.UV_WINS),
            _criterion("c", weight=3, verdict=Verdict.POETRY_WINS),
            _criterion("d", weight=2, verdict=Verdict.POETRY_WINS),
        ),
    )
    result = recommend(matrix)
    assert result.recommendation is Recommendation.EITHER_WORKS
    assert result.margin_ratio < 0.10


def test_recommend_returns_poetry_when_poetry_dominates() -> None:
    matrix = DecisionMatrix(
        name="poetry-heavy",
        criteria=(
            _criterion("a", weight=1, verdict=Verdict.UV_WINS),
            _criterion("b", weight=3, verdict=Verdict.POETRY_WINS),
            _criterion("c", weight=3, verdict=Verdict.POETRY_WINS),
        ),
    )
    result = recommend(matrix)
    assert result.recommendation is Recommendation.USE_POETRY_ISOLATED
    assert result.poetry_score > result.uv_score


def test_recommend_handles_empty_matrix_without_zero_division() -> None:
    result = recommend(DecisionMatrix(name="empty"))
    assert result.recommendation is Recommendation.EITHER_WORKS
    assert result.margin_ratio == 0.0
    assert result.total_weight == 0


def test_monorepo_scenario_favours_uv_more_strongly_than_default() -> None:
    default_result = recommend(default_matrix())
    monorepo_result = recommend(monorepo_scenario())
    assert monorepo_result.recommendation is Recommendation.USE_UV_WORKSPACE
    monorepo_diff = monorepo_result.uv_score - monorepo_result.poetry_score
    default_diff = default_result.uv_score - default_result.poetry_score
    assert monorepo_diff > default_diff


def test_multi_team_scenario_flips_the_recommendation_to_poetry() -> None:
    result = recommend(multi_team_scenario())
    assert result.recommendation is Recommendation.USE_POETRY_ISOLATED
    assert result.poetry_score > result.uv_score


def test_hybrid_scenario_returns_either_works() -> None:
    result = recommend(hybrid_scenario())
    assert result.recommendation is Recommendation.EITHER_WORKS


def test_scenario_by_name_dispatches_to_the_right_builder() -> None:
    assert scenario_by_name("monorepo").name == "monorepo"
    assert scenario_by_name("multi-team").name == "multi-team"
    assert scenario_by_name("hybrid").name == "hybrid"
    assert scenario_by_name("default").name == "default"


def test_scenario_by_name_rejects_unknown_scenarios() -> None:
    with pytest.raises(KeyError):
        scenario_by_name("does-not-exist")


def test_format_matrix_shows_header_and_one_line_per_criterion() -> None:
    matrix = default_matrix()
    text = format_matrix(matrix)
    header, *rows = text.splitlines()
    assert "uv=" in header and "poetry=" in header
    assert len(rows) == len(matrix.criteria)


def test_format_matrix_uses_distinct_marker_per_verdict() -> None:
    text = format_matrix(default_matrix())
    assert "[U]" in text
    assert "[P]" in text
    assert "[=]" in text


def test_format_recommendation_includes_pick_and_rationale() -> None:
    text = format_recommendation(recommend(default_matrix()))
    assert "recommendation:" in text
    assert "use-uv-workspace" in text
    assert "margin=" in text


def test_matrix_as_json_is_parseable_and_carries_recommendation() -> None:
    matrix = default_matrix()
    payload = json.loads(matrix_as_json(matrix))
    assert payload["uv_score"] == matrix.uv_score
    assert payload["poetry_score"] == matrix.poetry_score
    assert payload["tie_weight"] == matrix.tie_weight
    assert payload["total_weight"] == matrix.total_weight
    assert payload["recommendation"]["pick"] == "use-uv-workspace"
    assert len(payload["criteria"]) == 9


def test_matrix_as_json_serialises_verdicts_as_strings() -> None:
    payload = json.loads(matrix_as_json(default_matrix()))
    verdict_values = {row["verdict"] for row in payload["criteria"]}
    assert verdict_values <= {"uv-wins", "poetry-wins", "tie"}
