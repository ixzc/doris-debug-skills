import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug.audit import parse_audit_line

def test_kv_line():
    line = "Timestamp=2026-07-01 12:00:00 ClientIp=1.2.3.4 User=root QueryId=abc-def Time=15000 ScanBytes=1 ScanRows=2 Stmt=SELECT 1"
    r = parse_audit_line(line)
    assert r is not None
    assert r.query_id == "abc-def"
    assert r.query_time_ms == 15000
