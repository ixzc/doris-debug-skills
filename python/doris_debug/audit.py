"""Parse Doris FE audit log lines for slow / heavy queries.

FE audit fields vary by version; we support common pipe-delimited and key=value styles.
"""

from __future__ import annotations

import argparse
import re
from collections import namedtuple
from pathlib import Path
from typing import Iterable, Iterator, Optional

AuditRow = namedtuple(
    "AuditRow",
    "timestamp client user query_id query_time_ms scan_bytes scan_rows state stmt",
)


_KV_RE = re.compile(r"(\w+)=([^=]*?)(?=\s+\w+=|$)")


def _parse_kv(line: str) -> dict:
    return {m.group(1): m.group(2).strip() for m in _KV_RE.finditer(line)}


def parse_audit_line(line: str) -> Optional[AuditRow]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Prefer key=value (newer Doris audit)
    if "QueryId=" in line or "queryId=" in line or "Time=" in line:
        kv = _parse_kv(line)
        qid = kv.get("QueryId") or kv.get("queryId") or ""
        # Time often in ms
        t = kv.get("Time") or kv.get("QueryTime") or kv.get("latency") or "0"
        try:
            t_ms = float(re.sub(r"[^0-9.]", "", t) or 0)
        except ValueError:
            t_ms = 0.0
        scan_bytes = kv.get("ScanBytes") or kv.get("scanBytes") or "0"
        scan_rows = kv.get("ScanRows") or kv.get("scanRows") or "0"
        stmt = kv.get("Stmt") or kv.get("stmt") or kv.get("Sql") or ""
        ts = kv.get("Timestamp") or kv.get("time") or line[:19]
        return AuditRow(
            ts,
            kv.get("ClientIp") or kv.get("Client") or "",
            kv.get("User") or "",
            qid,
            t_ms,
            scan_bytes,
            scan_rows,
            kv.get("State") or "",
            stmt[:200],
        )
    # Fallback: pipe-delimited — best-effort positional
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 6:
        return None
    try:
        t_ms = float(re.sub(r"[^0-9.]", "", parts[4]) or 0)
    except ValueError:
        t_ms = 0.0
    return AuditRow(
        parts[0],
        parts[1] if len(parts) > 1 else "",
        parts[2] if len(parts) > 2 else "",
        parts[3] if len(parts) > 3 else "",
        t_ms,
        parts[5] if len(parts) > 5 else "",
        parts[6] if len(parts) > 6 else "",
        "",
        parts[-1][:200] if parts else "",
    )


def iter_audit(path: Path) -> Iterator[AuditRow]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            row = parse_audit_line(line)
            if row:
                yield row


def topk(path: Path, k: int = 20, min_ms: float = 0) -> list[AuditRow]:
    rows = [r for r in iter_audit(path) if r.query_time_ms >= min_ms]
    rows.sort(key=lambda r: r.query_time_ms, reverse=True)
    return rows[:k]


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Top-K slow queries from Doris fe.audit.log")
    p.add_argument("audit_log", type=Path)
    p.add_argument("-k", type=int, default=20)
    p.add_argument("--min-ms", type=float, default=1000)
    args = p.parse_args(list(argv) if argv is not None else None)
    for i, r in enumerate(topk(args.audit_log, args.k, args.min_ms), 1):
        print(
            f"{i:2d}. {r.query_time_ms:>10.0f}ms  qid={r.query_id}  "
            f"scanRows={r.scan_rows}  {r.stmt[:80]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
