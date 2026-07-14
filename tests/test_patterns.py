"""Test pattern regexes against real Doris log lines."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug import patterns


class TestExchangePatterns:
    def test_brpc_fail_match(self):
        line = "W20260715 10:00:00.123 failed to send brpc when exchange, dst=10.0.0.1:8060"
        assert patterns.EXCHANGE_BRPC_FAIL in line or _match(
            patterns.EXCHANGE_BRPC_FAIL, line
        )

    def test_e1008_match(self):
        line1 = "E20260715 10:00:00.123 [E1008] Reached timeout=60000"
        line2 = "W20260715 10:00:00.123 Reached timeout sending rpc"
        assert _match(patterns.BRPC_E1008, line1)
        assert _match(patterns.BRPC_E1008, line2)

    def test_brpc_stub_check_match(self):
        line = "W20260715 brpc stub: hand_shake check failed, remove brpc stub from cache"
        assert _match(patterns.BRPC_STUB_CHECK, line)


class TestCompactionPatterns:
    def test_too_many_versions_en(self):
        line = "E20260715 too many versions: version_count=2001 exceeds limit: max_tablet_version=2000"
        assert _match(patterns.TOO_MANY_VERSIONS, line)

    def test_235_error(self):
        line = "E20260715 Status: Error<TOO_MANY_VERSION> rowset cannot be added"
        assert _match(patterns.TOO_MANY_VERSIONS, line)


class TestMemoryPatterns:
    def test_memtracker_limiter(self):
        line = "W20260715 MemTrackerLimiter exceed limit. tracker:Query, consumption=64GB"
        assert _match(patterns.MEMTRACKER, line)

    def test_memory_limit_exceeded(self):
        line = "E20260715 memory limit exceeded: usage=80GB, limit=64GB"
        assert _match(patterns.MEMTRACKER, line)


class TestGroupCommitPatterns:
    def test_finish_group_commit(self):
        line = "I20260715 finish group commit, txn_id=12345, table=db.tbl"
        assert _match(patterns.GROUP_COMMIT_FINISH, line)

    def test_delete_wal_fail(self):
        line = "W20260715 fail to delete wal: path=/data/wal/xxx, err=No such file"
        assert _match(patterns.GROUP_COMMIT_DELETE_WAL_FAIL, line)


class TestFEPlanPatterns:
    def test_nereids_timeout(self):
        line = "W20260715 Nereids cost too much time: 32s, nereids_timeout_second=30"
        assert _match(patterns.NEREIDS_TIMEOUT, line)

    def test_query_timeout(self):
        line = "E20260715 query timeout: query_id=abc-123, elapsed=300s"
        assert _match(patterns.QUERY_TIMEOUT, line)


class TestNewPatterns:
    def test_clone_task(self):
        line = "I20260715 CLONE submit task: src=be1, dst=be2, tablet=10001"
        assert _match(patterns.CLONE_TASK, line)

    def test_s3_error(self):
        line = "E20260715 S3 error: Access Denied for bucket=doris-data"
        assert _match(patterns.S3_ERROR, line)

    def test_startup_error(self):
        line = "E20260715 fail to start BE: Address already in use: port=8060"
        assert _match(patterns.STARTUP_ERROR, line)


class TestDefaults:
    def test_sensible_defaults(self):
        assert patterns.DEFAULTS["max_tablet_version_num"] == 2000
        assert patterns.DEFAULTS["clone_worker_count"] == 3
        assert patterns.DEFAULTS["enable_brpc_connection_check"] is False

    def test_http_paths(self):
        assert patterns.BE_HTTP_PATHS["health"] == "/api/health"
        assert patterns.FE_HTTP_PATHS["bootstrap"] == "/api/bootstrap"


def _match(pattern: str, line: str) -> bool:
    import re
    return bool(re.search(pattern, line, re.I))
