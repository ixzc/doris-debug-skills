"""Inventory Group Commit WAL directories on a BE host.

WAL path defaults: <storage_root_path>/wal or config group_commit_wal_path
(see be/src/common/config.cpp group_commit_wal_path).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Optional


def dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def find_wal_dirs(roots: list[Path]) -> list[Path]:
    found = []
    for root in roots:
        if not root.exists():
            continue
        # explicit wal root
        if root.name == "wal" or (root / "wal").is_dir():
            found.append(root if root.name == "wal" else root / "wal")
            continue
        for p in root.rglob("wal"):
            if p.is_dir():
                found.append(p)
    # dedupe
    out, seen = [], set()
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Measure Doris group_commit WAL disk usage")
    p.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="storage_root_path(s) or explicit wal path(s)",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    dirs = find_wal_dirs(args.paths)
    if not dirs:
        print("No wal directories found under:", ", ".join(str(x) for x in args.paths))
        return 1
    grand = 0
    for d in dirs:
        sz = dir_size(d)
        grand += sz
        nfiles = sum(1 for _r, _d, files in os.walk(d) for _ in files)
        print(f"{sz / (1024**3):8.3f} GiB  files={nfiles:6d}  {d}")
    print(f"{grand / (1024**3):8.3f} GiB  TOTAL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
