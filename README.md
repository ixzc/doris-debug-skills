# doris-debug-skills

Apache Doris 生产排障 **Skill + 诊断 CLI + 案例库**。

按模块拆分 skill（`SKILL.md` + `references` / case），排查步骤与命令以 [apache/doris](https://github.com/apache/doris) 源码和运行机制为准。

## 里面有什么

| 组件 | 数量 | 说明 |
|------|------|------|
| `skills/*/SKILL.md` | 10 | Agent 可加载的排查 skill（Cause 分类 + Metric Taxonomy + 决策树） |
| `skills/*/references/` | **16** | 独立案例文件，Environment → Symptom → Investigation → Root Cause → Fix |
| `references/03-case-index.md` | **45** 条目 | 生产案例索引，按 8 个诊断域分类 |
| `references/04-metrics-guide.md` | 1 | 按域分类的关键指标速查（含告警阈值） |
| `references/05-config-quick-ref.md` | 1 | 按域分类的关键配置速查（含调参方向） |
| `references/02-source-map.md` | 1 | 现象 → 源码映射（含版本标注 + 升级风险表） |
| `python/doris_debug/` | 7 模块 | 可运行诊断 CLI（audit / metrics / wal / log-grep / patterns） |
| `guides/` | 2 | 跨模块级联排障 |
| `tests/` | 1 文件 | **16** 个正则签名验证测试 |

## Skills 一览

| Skill | 何时用 | 典型症状 | Case 数 |
|-------|--------|----------|---------|
| `query` | 慢查 / 超时 / Profile / Exchange WaitForData | Plan Time 超长、E11 brpc fanout、Scan 瓶颈 | **4** |
| `import` | Stream Load / Broker Load / Group Commit WAL | 307 重定向、RPC timed out、FE job 泄露 | **3** |
| `compaction` | `-235` / too many versions / score 高 | Base 残留、Cumu segfault、版本竞态 | **2** |
| `node` | OOM / crash / 内存泄漏 / False Alive | FileCache LRU 泄漏、Scanner 堆积、BDBJE 损坏 | **4** |
| `materialized-view` | sync MV / MTMV 刷新/改写 | Rewrite miss、分区不对齐、Struct invalid | **1** |
| `tablet` | Tablet 副本 / clone / 磁盘倾斜 | 统计异常、S3 冷热分离未清理 | - |
| `deployment` | FE/BE 启动失败 / 端口 / priority_networks | NPE 启动、配置不兼容 | - |
| `data-lake` | Hive/Iceberg/Paimon/Glue catalog | Pagination 丢失、分区表不识、谓词不下推 | **1** |
| `resource-isolation` | Workload Group / 队列 / spill | CME 异常（HashMap 并发）、cgroup 不准 | **1** |
| `cloud` | 存算分离 / meta-service / file cache | Warmup 空 batch、Plan 竞态、FDB 堆积 | **1** |

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

### 独立案例文件（16 个）

完整格式：Environment → Symptom → Key Evidence（日志片段）→ Investigation（排查步骤链）→ Root Cause → Fix → Key Diagnostic Actions

| 领域 | 案例 | 主题 |
|------|------|------|
| Query | case-001 | Exchange WaitForData timeout |
| Query | case-002 | Plan Time 10min — Nereids Iceberg Create Scan Range RPC 爆炸 |
| Query | case-003 | E11 Exchange brpc fanout — 高峰期 fragment 并发打满 |
| Import | case-001 | Group Commit WAL 堆积 |
| Import | case-002 | Import RPC timed out — BE Heavy Work Pool 打满 |
| Import | case-003 | INSERT INTO job 不清理导致 FE OOM |
| Compaction | case-001 | 累积 compaction 跟不上高频写入 |
| Compaction | case-002 | Schema Change 残留导致 Base Score 虚高 |
| Node | case-001 | jemalloc 碎片导致 OOM（MemTracker 未触发） |
| Node | case-002 | FileCache LRU Recorder 队列堆积 → 内存泄漏 |
| Node | case-003 | Scanner/Pipeline 堆积 + Runtime Filter 等待 → 内存持续增长 |
| Node | case-004 | FE BDBJE 损坏无法启动 + 恢复流程 |
| Cloud | case-001 | Warmup 后查询仍全量读 S3 — FE 下发空 Batch |
| Resource Isolation | case-001 | Workload Policy ConcurrentModificationException — SessionVariable HashMap 并发 |
| Data Lake | case-001 | Glue Catalog pagination 丢失 Database |
| Materialized View | case-001 | MTMV refresh 成功但 rewrite 始终不命中 |

### 案例索引（45 条目）

`references/03-case-index.md` 收录 45 个生产案例摘要，按 8 个诊断域分类，每个含 Symptom / Root cause / Fix / 关键诊断动作。

| 领域 | 条目 | 覆盖场景 |
|------|------|----------|
| Query | 7 | Plan Time、E11 fanout、计算组差异、结果跳变、Overwrite 冲突、CPU 异常 |
| Import | 6 | Heavy work pool、Arrow 格式、meta-service 慢、307 重定向、FE OOM |
| Compaction | 5 | SC 残留、Segfault、版本竞态、Ghost score、Cumu 单向高 |
| Node | 7 | 内存泄漏（3 种）、Coredump、BDBJE 损坏、Cache 泄漏、启动 200GB |
| Data Lake | 5 | Glue pagination、Iceberg transforms、JDBC pushdown、INSERT 慢 |
| Resource Isolation | 5 | Spill、cgroup 不准、Policy CME、MV Refresh WG、多 CG 绑定 |
| Cloud | 5 | Warmup miss、Plan 竞态、FDB 堆积、BE 异常重启、资源不释放 |
| Tablet / Deployment | 5 | 统计异常、冷热分离、EPOLLOUT、FE NPE、BE 配置启动失败 |

## 参考文档

| 文档 | 内容 |
|------|------|
| `01-common-commands.md` | 公共诊断命令（SHOW PROC、curl API、CLI） |
| `02-source-map.md` | 现象 → 源码映射（含 Doris 2.1/3.0 版本标注 + 升级风险表） |
| `03-case-index.md` | 45 个生产案例索引 |
| `04-metrics-guide.md` | 按域分类的关键指标速查（Query/Compaction/Node/Import/Cloud/Resource Isolation/FE） |
| `05-config-quick-ref.md` | 按域分类的关键配置速查（默认值 + 调参方向） |

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
6. 查 `references/04-metrics-guide.md` 确认关键指标含义和阈值
7. 查 `references/05-config-quick-ref.md` 确认配置参数和调参方向

## 测试

```bash
PYTHONPATH=python python3 -m pytest tests/ -v
# 16 passed — 验证 log-grep 签名模式能正确匹配真实日志
```

## License

Apache License 2.0
