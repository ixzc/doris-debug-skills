"""Log / metric patterns grounded in Apache Doris source messages.

References (apache/doris):
- be/src/exec/operator/exchange_sink_buffer.h  — "failed to send brpc when exchange"
- be/src/storage/rowset_builder.cpp           — TOO_MANY_VERSION / max_tablet_version_num
- be/src/service/http/action/reset_rpc_channel_action.cpp — /api/reset_rpc_channel
- be/src/runtime/fragment_mgr.cpp            — enable_brpc_connection_check hand_shake
- be/src/load/group_commit/group_commit_mgr.cpp — finish group commit / delete wal
- be/src/common/config.cpp                   — group_commit_* / max_tablet_version_num
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

# FE
NEREIDS_TIMEOUT = r"Nereids cost too much time|nereids_timeout"
GET_RESULT_TIMEOUT = r"get result timeout"
QUERY_TIMEOUT = r"query timeout|Query timeout"

# Profile counter names (pipeline)
PROFILE_WAIT_FOR_DATA = "WaitForData"
PROFILE_SHUFFLE_DEP = "SHUFFLE_DATA_DEPENDENCY"
PROFILE_PENDING_FINISH = "PendingFinishDependency"

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
}

BE_HTTP_PATHS = {
    "metrics": "/metrics",
    "reset_rpc_channel_all": "/api/reset_rpc_channel/all",
    "compaction_show": "/api/compaction/show",
    "vars": None,  # brpc builtin often on brpc_port (8060), not HTTP 8040
}
