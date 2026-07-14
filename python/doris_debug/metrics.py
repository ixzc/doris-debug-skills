"""Fetch and filter Doris BE/FE HTTP /metrics (Prometheus text format).

Supports threshold warnings for key Doris metrics.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from typing import Iterable, Optional

# Filter for diagnostic-relevant metrics
INTERESTING = re.compile(
    r"(compaction|tablet_version|memory|load|wal|query|scanner|brpc|rowset|memtable|"
    r"workload_group|file_cache|fragment|clone)",
    re.I,
)

# Key metrics with human-readable names and warning thresholds
THRESHOLDS: dict[str, tuple[str, str, Optional[float], Optional[float]]] = {
    # (metric_pattern, display_name, warn_low, warn_high)
    r"doris_be_memory_jemalloc_retained_bytes": (
        "jemalloc_retained", "bytes", None, None,
    ),
    r"doris_be_tablet_version_num_avg": (
        "avg_tablet_versions", "count", None, 1500.0,
    ),
    r"doris_be_compaction_score_max": (
        "max_compaction_score", "score", None, 100.0,
    ),
    r"doris_be_clone_task_count_total": (
        "clone_backlog", "count", None, 50.0,
    ),
}


def fetch_metrics(base: str, timeout: float = 10.0) -> str:
    url = base.rstrip("/") + "/metrics"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def filter_lines(text: str, pattern: Optional[re.Pattern] = None) -> list[str]:
    pat = pattern or INTERESTING
    out = []
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if pat.search(line):
            out.append(line)
    return out


def parse_metric_value(line: str) -> Optional[float]:
    """Extract the numeric value from a Prometheus metric line."""
    parts = line.rsplit(None, 1)
    if len(parts) == 2:
        try:
            return float(parts[1])
        except ValueError:
            pass
    return None


def check_thresholds(lines: list[str]) -> list[str]:
    """Check metric values against known thresholds, return warnings."""
    warnings: list[str] = []
    for pattern, (name, unit, warn_low, warn_high) in THRESHOLDS.items():
        for line in lines:
            if re.search(pattern, line):
                val = parse_metric_value(line)
                if val is not None:
                    if warn_low is not None and val < warn_low:
                        warnings.append(
                            f"WARN: {name} = {val} {unit} (low threshold: {warn_low})"
                        )
                    if warn_high is not None and val > warn_high:
                        warnings.append(
                            f"WARN: {name} = {val} {unit} (high threshold: {warn_high})"
                        )
                break  # one line per metric pattern
    return warnings


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Snapshot interesting Doris BE/FE /metrics"
    )
    p.add_argument(
        "--be", default="", help="BE URL, e.g. http://10.0.0.1:8040"
    )
    p.add_argument(
        "--fe", default="", help="FE URL, e.g. http://10.0.0.1:8030"
    )
    p.add_argument("--grep", default="", help="extra regex filter")
    p.add_argument(
        "--warn", action="store_true", help="show threshold warnings"
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    targets: list[str] = []
    if args.be:
        targets.append(args.be)
    if args.fe:
        targets.append(args.fe)
    if not targets:
        p.error("provide --be and/or --fe")

    pat = INTERESTING
    if args.grep:
        pat = re.compile(args.grep, re.I)

    exit_code = 0
    for target in targets:
        label = f"[{target.rstrip('/')}]"
        try:
            text = fetch_metrics(target)
        except Exception as e:
            print(f"ERROR {label}: {e}", file=sys.stderr)
            exit_code = 1
            continue
        lines = filter_lines(text, pat)
        if args.warn:
            for w in check_thresholds(lines):
                print(f"{label} {w}")
        print(f"\n{label} ({len(lines)} relevant metrics)")
        for line in lines:
            print(line)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
