# Doris Source Map（排障 ↔ 源码）

| 现象 | 源码位置 | Skill |
|------|----------|-------|
| `failed to send brpc when exchange` | `be/src/exec/operator/exchange_sink_buffer.h` | query |
| `reset_rpc_channel` 只清 internal cache | `be/src/service/http/action/reset_rpc_channel_action.cpp` | query |
| brpc stub hand_shake / erase cache | `be/src/runtime/fragment_mgr.cpp` (`_check_brpc_available`) | query |
| `enable_brpc_connection_check` | `be/src/common/config.cpp` | query |
| Group Commit finish + `delete_wal` | `be/src/load/group_commit/group_commit_mgr.cpp` | import |
| `group_commit_*` BE 配置 | `be/src/common/config.cpp` (~1407+) | import |
| TOO_MANY_VERSION / `-235` 文案 | `be/src/storage/rowset_builder.cpp` `check_tablet_version_count` | compaction / import |
| `max_tablet_version_num` default 2000 | `be/src/common/config.cpp` | compaction |
| WaitForData counter | exchange source operator Profile | query |
| Nereids timeout session | `fe/.../SessionVariable.java` `nereids_timeout_second` | query |
| MTMV 服务 | `fe/.../mtmv/MTMVService.java` | materialized-view |
| Sync MV alter | `fe/.../alter/MaterializedViewHandler.java` | materialized-view |

版本差异以你部署的分支为准；排障结论应能在源码中找到对应错误字符串或配置项。
