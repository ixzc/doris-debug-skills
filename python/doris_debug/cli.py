"""doris-debug CLI entrypoint."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: doris-debug <command> ...\n"
            "Commands:\n"
            "  audit-topk   Top slow queries from fe.audit.log\n"
            "  be-metrics   Snapshot BE /metrics\n"
            "  wal-du       Measure group_commit WAL directories\n"
            "  log-grep     Grep FE/BE logs by query_id or signature pack\n"
        )
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "audit-topk":
        from .audit import main as m
    elif cmd == "be-metrics":
        from .metrics import main as m
    elif cmd == "wal-du":
        from .wal import main as m
    elif cmd == "log-grep":
        from .loggrep import main as m
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 2
    return m(rest)


if __name__ == "__main__":
    raise SystemExit(main())
