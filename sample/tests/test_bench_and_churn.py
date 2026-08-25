"""Unit-test the pure logic of the step-5 measurement harness.

The bench harness shells out to `uv` and `poetry`, which cannot run
inside pytest without network. We test only the deterministic pieces:
the `Measurement.median` aggregation, the row formatting, the summary
grouping, and the churn analyzer against hand-crafted lockfile
fixtures that we own end-to-end.
"""
from __future__ import annotations

from textwrap import dedent

from bench_install import Measurement, format_row, summarize, total_by_kind
from measure_churn import (
    format_report,
    line_churn,
    package_churn,
    parse_pins,
)


LOCK_BEFORE = dedent(
    """\
    version = 1

    [[package]]
    name = "pytest"
    version = "8.4.2"

    [[package]]
    name = "pluggy"
    version = "1.6.0"

    [[package]]
    name = "iniconfig"
    version = "2.3.0"
    """
)

LOCK_AFTER = dedent(
    """\
    version = 1

    [[package]]
    name = "pytest"
    version = "9.1.1"

    [[package]]
    name = "pluggy"
    version = "1.6.0"

    [[package]]
    name = "packaging"
    version = "26.3"
    """
)


def test_parse_pins_reads_name_and_version_blocks() -> None:
    pins = parse_pins(LOCK_BEFORE)
    assert pins == {"pytest": "8.4.2", "pluggy": "1.6.0", "iniconfig": "2.3.0"}


def test_package_churn_detects_added_removed_and_upgraded() -> None:
    churn = package_churn(LOCK_BEFORE, LOCK_AFTER)
    assert churn.added == {"packaging": "26.3"}
    assert churn.removed == {"iniconfig": "2.3.0"}
    assert churn.upgraded == {"pytest": ("8.4.2", "9.1.1")}
    assert churn.total_changed == 3


def test_line_churn_counts_added_and_removed_lines() -> None:
    added, removed = line_churn(LOCK_BEFORE, LOCK_AFTER)
    # pytest version line + iniconfig block (name+version+blank+header) swap
    # for packaging block, so both counts are strictly positive and equal-ish.
    assert added > 0
    assert removed > 0


def test_line_churn_is_zero_for_identical_text() -> None:
    added, removed = line_churn(LOCK_BEFORE, LOCK_BEFORE)
    assert (added, removed) == (0, 0)


def test_format_report_includes_label_and_counts() -> None:
    report = format_report("uv.lock", LOCK_BEFORE, LOCK_AFTER)
    assert report.startswith("uv.lock:")
    assert "3 packages changed" in report
    assert "pytest" in report


def test_measurement_median_uses_middle_value() -> None:
    m = Measurement("uv-workspace", "uv", "cold", seconds=[0.5, 1.0, 1.5])
    assert m.median == 1.0


def test_measurement_median_handles_empty_series() -> None:
    m = Measurement("uv-workspace", "uv", "cold")
    assert m.median == 0.0


def test_format_row_shows_scenario_and_median() -> None:
    row = format_row(Measurement("uv-workspace", "uv", "cold", seconds=[1.23]))
    assert "uv-workspace" in row
    assert "cold" in row
    assert "median=  1.23s" in row
    assert "runs=1" in row


def test_summarize_groups_medians_by_scenario_and_kind() -> None:
    measurements = [
        Measurement("uv-workspace", "uv", "cold", seconds=[2.0]),
        Measurement("uv-workspace", "uv", "warm", seconds=[0.5]),
        Measurement("poetry-app", "poetry", "cold", seconds=[8.0]),
    ]
    grouped = summarize(measurements)
    assert grouped["uv-workspace"] == {"cold": 2.0, "warm": 0.5}
    assert grouped["poetry-app"] == {"cold": 8.0}


def test_total_by_kind_sums_only_matching_tool_and_kind() -> None:
    measurements = [
        Measurement("poetry-shared_lib", "poetry", "cold", seconds=[6.0]),
        Measurement("poetry-app", "poetry", "cold", seconds=[7.0]),
        Measurement("poetry-app", "poetry", "warm", seconds=[1.0]),
        Measurement("uv-workspace", "uv", "cold", seconds=[100.0]),
    ]
    assert total_by_kind(measurements, "poetry", "cold") == 13.0
    assert total_by_kind(measurements, "poetry", "warm") == 1.0
    assert total_by_kind(measurements, "uv", "warm") == 0.0
