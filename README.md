# doris-debug-skills

Apache Doris 生产排障 **Skill + 诊断代码**。

按模块拆分 skill（`SKILL.md` + `references` / case），排查步骤与命令以 [apache/doris](https://github.com/apache/doris) 源码和运行机制为准。

## 里面有什么

| 组件 | 说明 |
|------|------|
| `skills/*` | Agent 可加载的排查流程（Cause 分类 + Doris 命令） |
| `python/doris_debug/` | 可运行诊断库 / CLI |
| `references/` | 公共命令、源码索引 |
| `guides/` | 跨模块级联排障 |

## 快速用 CLI

```bash
export PYTHONPATH=$PWD/python
./scripts/doris-debug audit-topk /path/to/fe.audit.log -k 20 --min-ms 3000
./scripts/doris-debug be-metrics --be http://127.0.0.1:8040
./scripts/doris-debug wal-du /path/to/be/storage
./scripts/doris-debug log-grep /path/to/be/log --pack exchange --query-id 'xxxx-xxxx'
```

或：

```bash
PYTHONPATH=python python3 -m doris_debug wal-du /data/doris/be/storage
```

## Skills 一览

| Skill | 何时用 | 关键 Doris 源码锚点 |
|-------|--------|---------------------|
| `query` | 慢查 / 超时 / Profile / Exchange WaitForData | Nereids、Profile、`exchange_sink_buffer.h` |
| `import` | Stream Load / Group Commit WAL | `group_commit_mgr.cpp`, `config.cpp` |
| `compaction` | `-235` / too many versions | `rowset_builder.cpp`, `max_tablet_version_num` |
| `node` | OOM / crash / Alive | memtracker / FE JVM |
| `materialized-view` | sync MV / MTMV | `mtmv/`, rollup handler |
| `tablet` / `deployment` / `data-lake` / `resource-isolation` / `cloud` | 对应场景 | 见各 SKILL.md |

路由入口安装后为 `doris-debug`（见 `scripts/install.sh`）。

## 安装到 Claude Code / Cursor

```bash
./scripts/install.sh --tool claude-code --target ~/.claude/skills/
./scripts/install.sh --tool cursor --target .cursor/rules/
```

## 方法论

1. Client → FE → BE → Disk/Network 自上而下  
2. 日志 / metrics / Profile / `SHOW PROC` 证据优先  
3. 先止血（限流、kill、`reset_rpc_channel`）再根因  
4. 对照 `references/02-source-map.md` 回源码验证假设  

## License

Apache License 2.0
