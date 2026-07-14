"""Fetch and filter Doris BE HTTP /metrics (Prometheus text format)."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from typing import Iterable, Optional


INTERESTING = re.compile(
    r"(compaction|tablet_version|memory|load|wal|query|scanner|brpc|rowset|memtable)",
    re.I,
)


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


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Snapshot interesting Doris BE /metrics")
    p.add_argument("--be", required=True, help="e.g. http://10.0.0.1:8040")
    p.add_argument("--grep", default="", help="extra regex filter")
    args = p.parse_args(list(argv) if argv is not None else None)
    try:
        text = fetch_metrics(args.be)
    except Exception as e:
        print(f"ERROR fetching {args.be}/metrics: {e}", file=sys.stderr)
        return 1
    pat = INTERESTING
    if args.grep:
        pat = re.compile(args.grep, re.I)
    for line in filter_lines(text, pat):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
