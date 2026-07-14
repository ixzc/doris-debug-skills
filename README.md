# doris-debug-skills

Apache Doris 生产排障 **Skill + 诊断 CLI + 案例库**。

按模块拆分 skill（`SKILL.md` + `references` / case），排查步骤与命令以 [apache/doris](https://github.com/apache/doris) 源码和运行机制为准。

## 里面有什么

| 组件 | 说明 |
|------|------|
| `skills/*` | 10 个 Agent 可加载的排查 skill（Cause 分类 + 决策树 + Metric Taxonomy） |
| `skills/*/references/` | 5 个案例文件，Symptom / Root cause / Fix 格式 |
| `python/doris_debug/` | 可运行诊断 CLI（audit / metrics / wal / log-grep） |
| `references/` | 公共命令、源码索引（含版本标注）、43 个生产案例索引 |
| `guides/` | 跨模块级联排障 |
| `tests/` | 57 个单元测试，覆盖 patterns / audit / wal / loggrep / metrics |

## Skills 一览

| Skill | 何时用 | 典型症状 |
|-------|--------|----------|
| `query` | 慢查 / 超时 / Profile / Exchange WaitForData | Plan Time 超长、E11 brpc fanout、Scan 瓶颈 |
| `import` | Stream Load / Broker Load / Group Commit WAL | 307 重定向、RPC timed out、FE job 泄露 |
| `compaction` | `-235` / too many versions / score 高 | Base 残留、Cumu segfault、版本竞态 |
| `node` | OOM / crash / 内存泄漏 / False Alive | file_cache 泄漏、auto_analyze OOM、BDBJE 损坏 |
| `materialized-view` | sync MV / MTMV 刷新/改写 | Rewrite miss、分区不对齐、Struct invalid |
| `tablet` | Tablet 副本 / clone / 磁盘倾斜 | 统计异常、S3 冷热分离未清理 |
| `deployment` | FE/BE 启动失败 / 端口 / priority_networks | NPE 启动、配置不兼容 |
| `data-lake` | Hive/Iceberg/Paimon/Glue catalog | Pagination 丢失、分区表不识、谓词不下推 |
| `resource-isolation` | Workload Group / 队列 / spill | CME 异常、cgroup 不准、Spill 不生效 |
| `cloud` | 存算分离 / meta-service / file cache | Warmup miss、Plan 竞态、FDB 堆积 |

路由入口安装后为 `doris-debug`。

## 快速用 CLI

```bash
export PYTHONPATH=$PWD/python

# 慢查询 Top-K
./scripts/doris-debug audit-topk fe/log/fe.audit.log -k 20 --min-ms 5000

# BE/FE 指标快照 + 阈值告警
./scripts/doris-debug be-metrics --be http://127.0.0.1:8040 --grep compaction --warn
./scripts/doris-debug be-metrics --fe http://127.0.0.1:8030 --warn

# Group Commit WAL 磁盘用量
./scripts/doris-debug wal-du /path/to/be/storage

# 日志检索：按 query_id + 签名包 + 跨文件 fragment 关联
./scripts/doris-debug log-grep be/log --query-id 'xxxx-xxxx' --pack exchange --correlate
```

## 案例库

`references/03-case-index.md` 收录 43 个生产案例，按 Skill 领域分类：

| 领域 | 案例数 | 覆盖场景 |
|------|--------|----------|
| Query | 7 | Plan Time 10min、E11 brpc fanout、计算组差异、结果跳变 |
| Import | 6 | Heavy work pool 超时、Arrow 格式、meta-service 慢 |
| Compaction | 5 | SC 残留、Segfault、版本竞态、Ghost score |
| Node | 7 | 内存泄漏、Coredump、BDBJE 损坏、Cache 泄漏 |
| Data Lake | 5 | Glue pagination、Iceberg transforms、JDBC pushdown |
| Resource Isolation | 5 | Spill 不生效、cgroup 不准、Policy CME |
| Cloud | 5 | Warmup miss、Plan 竞态、FDB 堆积、BE 异常重启 |
| Tablet / Deployment | 5 | 统计异常、冷热分离、EPOLLOUT 超时、BE 启动失败 |

每个案例含 Symptom / Root cause / Fix / 关键诊断动作。

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
5. 查 `references/03-case-index.md` 匹配已知案例，避免重复排查

## 测试

```bash
PYTHONPATH=python python3 -m pytest tests/ -v
# 57 passed
```

## License

Apache License 2.0
