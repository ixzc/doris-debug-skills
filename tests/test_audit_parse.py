"""Test audit log parsing for kv and pipe-delimited formats."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug.audit import parse_audit_line, iter_audit, topk


def test_kv_line():
    line = "Timestamp=2026-07-01 12:00:00 ClientIp=1.2.3.4 User=root QueryId=abc-def Time=15000 ScanBytes=1 ScanRows=2 Stmt=SELECT 1"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_id == "abc-def"
    assert r.query_time_ms == 15000


def test_kv_line_alternate_keys():
    line = "Timestamp=2026-07-01 12:00:00 Client=10.0.0.1 User=admin queryId=xyz-789 QueryTime=3200 scanBytes=1024 scanRows=500 State=OK Stmt=SELECT * FROM t"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_id == "xyz-789"
    assert r.query_time_ms == 3200
    assert r.scan_bytes == "1024"
    assert r.state == "OK"


def test_pipe_delimited():
    line = "2026-07-01 12:00:00 | 1.2.3.4 | root | abc-123 | 5000 | 1024 | 100 | EOF | SELECT * FROM t"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_id == "abc-123"
    assert r.query_time_ms == 5000


def test_comment_line():
    assert parse_audit_line("# audit log header") is None
    assert parse_audit_line("") is None


def test_short_pipe_line():
    assert parse_audit_line("a|b|c") is None


def test_time_parsing_with_ms_suffix():
    line = "Timestamp=2026-07-01 12:00:00 User=root QueryId=q1 Time=3250ms ScanBytes=0 ScanRows=0 Stmt=x"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_time_ms == 3250


def test_time_with_unit():
    line = "Timestamp=2026-07-01 User=root QueryId=q2 Time=12.5s ScanBytes=0 ScanRows=0 Stmt=x"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_time_ms == 12.5  # raw value, unit normalization not implemented


def test_stmt_truncation():
    long_stmt = "SELECT " + "x, " * 500
    line = f"Timestamp=2026-07-01 User=root QueryId=q3 Time=100 Stmt={long_stmt}"
    r = parse_audit_line(line)
    assert r is not None
    assert len(r.stmt) <= 200


def test_iter_audit():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(
            "Timestamp=2026-07-01 12:00:00 ClientIp=1.2.3.4 User=root QueryId=aaa Time=1000 ScanBytes=0 ScanRows=0 Stmt=SELECT 1\n"
            "Timestamp=2026-07-01 12:00:01 ClientIp=1.2.3.4 User=root QueryId=bbb Time=5000 ScanBytes=0 ScanRows=0 Stmt=SELECT 2\n"
            "# a comment\n"
            "Timestamp=2026-07-01 12:00:02 ClientIp=1.2.3.4 User=root QueryId=ccc Time=200 ScanBytes=0 ScanRows=0 Stmt=SELECT 3\n"
        )
        f.flush()
        f_path = Path(f.name)
    try:
        rows = list(iter_audit(f_path))
        assert len(rows) == 3
    finally:
        f_path.unlink()


def test_topk():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(
            "Timestamp=2026-07-01 12:00:00 User=root QueryId=a Time=100 Stmt=x\n"
            "Timestamp=2026-07-01 12:00:01 User=root QueryId=b Time=500 Stmt=y\n"
            "Timestamp=2026-07-01 12:00:02 User=root QueryId=c Time=300 Stmt=z\n"
        )
        f.flush()
        f_path = Path(f.name)
    try:
        rows = topk(f_path, k=2)
        assert len(rows) == 2
        assert rows[0].query_time_ms == 500
        assert rows[1].query_time_ms == 300
    finally:
        f_path.unlink()


def test_topk_min_ms_filter():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(
            "Timestamp=2026-07-01 12:00:00 User=root QueryId=a Time=100 Stmt=x\n"
            "Timestamp=2026-07-01 12:00:01 User=root QueryId=b Time=500 Stmt=y\n"
        )
        f.flush()
        f_path = Path(f.name)
    try:
        rows = topk(f_path, k=10, min_ms=300)
        assert len(rows) == 1
        assert rows[0].query_id == "b"
    finally:
        f_path.unlink()
