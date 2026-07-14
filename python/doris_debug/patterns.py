"""Log / metric patterns grounded in Apache Doris source messages.

References (apache/doris):
- be/src/exec/operator/exchange_sink_buffer.h  — "failed to send brpc when exchange"
- be/src/storage/rowset_builder.cpp           — TOO_MANY_VERSION / max_tablet_version_num
- be/src/service/http/action/reset_rpc_channel_action.cpp — /api/reset_rpc_channel
- be/src/runtime/fragment_mgr.cpp            — enable_brpc_connection_check hand_shake
- be/src/load/group_commit/group_commit_mgr.cpp — finish group commit / delete wal
- be/src/common/config.cpp                   — group_commit_* / max_tablet_version_num
- be/src/runtime/memory/mem_tracker_limiter.cpp — MemTrackerLimiter
- be/src/agent/task_worker_pool.cpp          — clone worker
- be/src/util/cgroup_util.cpp                — cgroup adapter
"""

from __future__ import annotations

# BE WARNING / INFO
EXCHANGE_BRPC_FAIL = r"failed to send brpc when exchange"
BRPC_E1008 = r"\[E1008\]|Reached timeout"
BRPC_STUB_CHECK = r"brpc stub:.*check failed|remove brpc stub from cache"
GROUP_COMMIT_FINISH = r"finish group commit"
GROUP_COMMIT_DELETE_WAL_FAIL = r"fail to delete wal"
TOO_MANY_VERSIONS = r"too many versions|TOO_MANY_VERSION|exceed limit:.*max_tablet_version"
PUBLISH_TIMEOUT = r"publish.?timeout|PUBLISH_TIMEOUT"
MEMTRACKER = r"MemTrackerLimiter|memory limit exceeded|Cancel.*memory"
CLONE_TASK = r"clone.*task|CLONE.*submit|clone.*fail"
CGROUP_INIT_FAIL = r"cgroup.*fail|cgroup.*error|init cgroup"
FILE_CACHE_ERROR = r"file_cache.*error|file_cache.*fail|local.?cache.*error"
S3_ERROR = r"403|Access Denied|SlowDown|Throughput.*exceed|NoSuchBucket"
SCHEMA_MISMATCH = r"schema.*mismatch|column.*type.*mismatch|parquet.*schema"
STARTUP_ERROR = r"fail to start|Address already in use|Permission denied|No such file"

# FE
NEREIDS_TIMEOUT = r"Nereids cost too much time|nereids_timeout"
GET_RESULT_TIMEOUT = r"get result timeout"
QUERY_TIMEOUT = r"query timeout|Query timeout"
FE_OOM = r"OutOfMemoryError|GC overhead|heap space"
METADATA_CORRUPT = r"image.*corrupt|edit.*log.*corrupt|meta.*recovery"
BDBJE_ERROR = r"BDB.*error|JE.*error|Environment.*failure"

# Profile counter names (pipeline)
PROFILE_WAIT_FOR_DATA = "WaitForData"
PROFILE_SHUFFLE_DEP = "SHUFFLE_DATA_DEPENDENCY"
PROFILE_PENDING_FINISH = "PendingFinishDependency"
PROFILE_SPILL_DATA_SIZE = "SpillDataSize"
PROFILE_SCANNER_BLOCK_TIME = "ScannerGetBlockTime"

# Defaults from be/src/common/config.cpp (document only; live value from BE)
DEFAULTS = {
    "max_tablet_version_num": 2000,
    "time_series_max_tablet_version_num": 20000,
    "group_commit_insert_threads": 10,
    "group_commit_relay_wal_threads": 10,
    "group_commit_queue_mem_limit": 67108864,
    "group_commit_wal_max_disk_limit": "10%",
    "enable_brpc_connection_check": False,
    "brpc_connection_check_timeout_ms": 10000,
    "clone_worker_count": 3,
    "mem_limit": "80%",
    "enable_je_purge": False,
}

BE_HTTP_PATHS = {
    "metrics": "/metrics",
    "reset_rpc_channel_all": "/api/reset_rpc_channel/all",
    "compaction_show": "/api/compaction/show",
    "vars": None,  # brpc builtin often on brpc_port (8060), not HTTP 8040
    "health": "/api/health",
}

FE_HTTP_PATHS = {
    "metrics": "/metrics",
    "health": "/api/health",
    "bootstrap": "/api/bootstrap",
    "query_profile": "/api/query_profile",
}
