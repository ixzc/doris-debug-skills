"""Test metrics: filtering, threshold warnings, and fetch stub."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug.metrics import (
    filter_lines,
    parse_metric_value,
    check_thresholds,
    INTERESTING,
)


class TestFilterLines:
    def test_skips_comments_and_empty(self):
        lines = filter_lines("# HELP some_metric", INTERESTING)
        assert lines == []

        lines = filter_lines("", INTERESTING)
        assert lines == []

    def test_keeps_interesting(self):
        text = (
            "# HELP doris_be_compaction_bytes_total\n"
            "doris_be_compaction_bytes_total 12345\n"
            "doris_be_http_requests 678\n"
            "doris_be_tablet_version_num_avg 42\n"
        )
        lines = filter_lines(text)
        line_text = "\n".join(lines)
        assert "compaction" in line_text
        assert "tablet_version" in line_text
        assert "http_requests" not in line_text  # not in INTERESTING

    def test_custom_pattern(self):
        import re
        text = "doris_be_foo 1\ndoris_be_bar 2\nother 3"
        lines = filter_lines(text, re.compile(r"foo|bar"))
        assert len(lines) == 2


class TestParseMetricValue:
    def test_simple_value(self):
        assert parse_metric_value("metric_name 42.5") == 42.5

    def test_with_labels(self):
        assert parse_metric_value(
            'metric{label="value"} 99.9'
        ) == 99.9

    def test_invalid(self):
        import math
        val = parse_metric_value("metric_name NaN")
        assert val is None or math.isnan(val)
        assert parse_metric_value("metric_name") is None


class TestCheckThresholds:
    def test_high_warning(self):
        lines = ["doris_be_tablet_version_num_avg 1800"]
        warnings = check_thresholds(lines)
        assert len(warnings) >= 1
        assert any("avg_tablet_versions" in w for w in warnings)
        assert any("1800" in w for w in warnings)

    def test_no_warning_within_limit(self):
        lines = ["doris_be_tablet_version_num_avg 500"]
        warnings = check_thresholds(lines)
        assert len(warnings) == 0  # 500 < 1500 threshold

    def test_multiple_violations(self):
        lines = [
            "doris_be_tablet_version_num_avg 1900",
            "doris_be_compaction_score_max 250",
            "doris_be_clone_task_count_total 120",
        ]
        warnings = check_thresholds(lines)
        assert len(warnings) >= 3


class TestInterestingPattern:
    def test_covers_key_metrics(self):
        samples = [
            "doris_be_compaction_score_max",
            "doris_be_tablet_version_num_avg",
            "doris_be_memory_jemalloc_retained_bytes",
            "doris_be_load_bytes",
            "doris_be_wal_size_bytes",
            "doris_be_query_scan_bytes",
            "doris_be_scanner_thread_count",
            "doris_be_brpc_connection_count",
            "doris_be_rowset_count",
            "doris_be_memtable_bytes",
            "doris_be_workload_group_queries",
            "doris_be_file_cache_hit_ratio",
            "doris_be_fragment_count",
            "doris_be_clone_task_count",
        ]
        for sample in samples:
            assert INTERESTING.search(sample), (
                f"INTERESTING pattern should match: {sample}"
            )
