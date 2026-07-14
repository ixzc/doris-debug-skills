"""Grep Doris FE/BE logs for a query_id or known failure signatures."""

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
}


def grep_files(files: list[Path], regexes: list[str], max_hits: int = 200) -> list[str]:
    compiled = [re.compile(r, re.I) for r in regexes]
    hits = []
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


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Grep Doris logs by query_id or signature pack")
    p.add_argument("log_paths", nargs="+", type=Path)
    p.add_argument("--query-id", default="")
    p.add_argument(
        "--pack",
        choices=sorted(SIGNATURES.keys()),
        action="append",
        default=[],
        help="Named signature pack from doris_debug.patterns",
    )
    p.add_argument("--max-hits", type=int, default=200)
    args = p.parse_args(list(argv) if argv is not None else None)

    regexes: list[str] = []
    if args.query_id:
        regexes.append(re.escape(args.query_id))
    for pack in args.pack:
        regexes.extend(SIGNATURES[pack])
    if not regexes:
        p.error("provide --query-id and/or --pack")

    files: list[Path] = []
    for path in args.log_paths:
        if path.is_dir():
            files.extend(sorted(path.glob("**/*")))
        else:
            files.append(path)

    for hit in grep_files(files, regexes, args.max_hits):
        print(hit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
