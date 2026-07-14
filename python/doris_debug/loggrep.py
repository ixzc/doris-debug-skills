"""Grep Doris FE/BE logs for a query_id or known failure signatures.

Supports --query-id with automatic fragment_instance_id extraction
for cross-file correlation across FE audit + BE logs.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional

from . import patterns

SIGNATURES = {
    "exchange": [patterns.EXCHANGE_BRPC_FAIL, patterns.BRPC_E1008, patterns.BRPC_STUB_CHECK],
    "versions": [patterns.TOO_MANY_VERSIONS],
    "group_commit": [patterns.GROUP_COMMIT_FINISH, patterns.GROUP_COMMIT_DELETE_WAL_FAIL],
    "planner": [patterns.NEREIDS_TIMEOUT, patterns.GET_RESULT_TIMEOUT],
    "memory": [patterns.MEMTRACKER],
    "all": [],  # special: match all lines (use with --query-id alone)
}

# Fragment instance ID: "fragment_instance_id=" or "InstanceId=" or hex(16)
_FRAGMENT_ID_RE = re.compile(
    r"(?:fragment_instance_id|InstanceId)\s*[:=]\s*([a-z0-9-]{6,})",
    re.I,
)
_QUERY_ID_FIELD_RE = re.compile(
    r"(?:QueryId|query_id|queryId)\s*[:=]\s*([a-f0-9-]{16,})",
    re.I,
)


def extract_fragment_ids(lines: list[str]) -> set[str]:
    """Extract fragment_instance_id values from log lines."""
    ids: set[str] = set()
    for line in lines:
        m = _FRAGMENT_ID_RE.search(line)
        if m:
            ids.add(m.group(1))
    return ids


def grep_files(
    files: list[Path],
    regexes: list[str],
    max_hits: int = 200,
) -> list[str]:
    compiled = [re.compile(r, re.I) for r in regexes]
    hits: list[str] = []
    for fp in files:
        if not fp.is_file():
            continue
        try:
            with fp.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if any(c.search(line) for c in compiled):
                        hits.append(f"{fp}:{i}:{line.rstrip()}")
                        if len(hits) >= max_hits:
                            return hits
        except OSError as e:
            hits.append(f"ERROR reading {fp}: {e}")
    return hits


def _find_log_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            # Prefer .log / .WARNING / .INFO files; skip __pycache__ etc.
            for pattern in ["*.log", "*.log.*", "*.WARNING", "*.INFO"]:
                files.extend(sorted(path.glob(pattern)))
            # Also catch file without extension
            for child in sorted(path.iterdir()):
                if child.is_file() and child.name not in {
                    f.name for f in files
                }:
                    files.append(child)
        elif path.is_file():
            files.append(path)
    return files


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Grep Doris logs by query_id or signature pack"
    )
    p.add_argument("log_paths", nargs="+", type=Path)
    p.add_argument("--query-id", default="")
    p.add_argument(
        "--pack",
        choices=sorted(SIGNATURES.keys()),
        action="append",
        default=[],
        help="Named signature pack from doris_debug.patterns",
    )
    p.add_argument(
        "--correlate",
        action="store_true",
        help="After finding query_id hits, also grep for extracted fragment_instance_ids",
    )
    p.add_argument("--max-hits", type=int, default=200)
    args = p.parse_args(list(argv) if argv is not None else None)

    regexes: list[str] = []
    if args.query_id:
        regexes.append(re.escape(args.query_id))
    for pack_name in args.pack:
        regexes.extend(SIGNATURES[pack_name])
    if not regexes:
        p.error("provide --query-id and/or --pack")

    files = _find_log_files(args.log_paths)

    hits = grep_files(files, regexes, args.max_hits)
    for hit in hits:
        print(hit)

    # Second pass: if --correlate, also search for fragment_instance_ids
    if args.correlate and args.query_id and hits:
        frag_ids = extract_fragment_ids(hits)
        if frag_ids:
            print("\n--- fragment correlation ---")
            frag_regexes = [re.escape(fid) for fid in frag_ids]
            corr_hits = grep_files(
                files, frag_regexes, args.max_hits - len(hits),
            )
            for hit in corr_hits:
                print(hit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
