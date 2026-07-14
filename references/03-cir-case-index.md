# CIR Case Index（Jira 生产案例 → Skill 映射）

> 数据来源：Jira CIR 项目 (http://jira.selectdb-in.cc/)，共计 20,000+ issue。
> 本文档按 doris-debug skill 分类，列出具有诊断参考价值的典型案例及关键模式。

## 统计概览

| 诊断域 | Jira 标签 | 关键案例数 | 代表性模式 |
|--------|-----------|-----------|-----------|
| Query | `查询`, `查询执行小组`, `timeout`, `慢查询` | 4 | Plan 超时 / Scan 瓶颈 / Join broadcast OOM / 结果跳变 |
| Import | `导入`, `streamload`, `brokerload`, `routine_load` | 4 | 307 重定向 / FE OOM 泄露 / publish timeout / S3 load 慢 |
| Compaction | `compaction`, `-235`, `版本过多` | 4 | SC 残留 base score / cumu score 高 / segfault / 版本 compacted |
| Node | `内存`, `OOM`, `FE挂`, `crash` | 4 | auto_analyze OOM / 内存泄漏 / FE NPE / FE bdbje 损坏 |
| Tablet | `存储小组`, `tablet`, `冷热分层` | 3 | tablet 统计异常 / S3 数据未清理 / 写入超时 |
| Deployment | `FE`, `startup` | 2 | FE bdbje 损坏 / NPE 启动失败 |
| Data Lake | `数据湖`, `iceberg`, `hive`, `glue` | 3 | Iceberg plan 慢 / glue catalog 404 / 谓词下推缺失 |
| Resource Isolation | `workload_group` | 1 | spill disk / memory tracking 不准 |
| Cloud | `cloud`, `存算分离` | 2 | 查询卡住 plan 竞态 / BE 资源不释放 |

---

## Query（查询诊断）

### case-002: FE Nereids Plan Time 超长（Iceberg 外表）

- **Jira**: [CIR-20967] 【海外-spinny】plan time超长
- **标签**: `ai_new_issue`, `海外`
- **Symptom**: 查询总耗时 10min8s，`Plan Time=10min8sec`，BE 实际执行只有 214ms/1MB 数据
- **Root cause**: Nereids `Finalize Scan Node → Create Scan Range` 阶段对 Iceberg 外表耗时 10min，64 个文件、63 个分区，每次 `getManifestFiles` 调用了 `UpdateRunningStatus` 触发 `msClient.updateInstance`——每一次 RPC 消耗 ~200ms，针对大量 Iceberg partition 反复调用 → 10min+
- **Fix**: 短期：调大 manifest 缓存 (`iceberg_manifest_cache_refresh_interval_s`)；长期：改进 scan range 创建阶段减少重复 RPC
- **Evidence**: Profile `Finalize Scan Node Time=10min8sec`, `Get Splits Time=6sec`, `Create Scan Range Time=10min1sec`
- **关键诊断动作**: 1) Profile → Plan Time 占比 2) 确认 Is Nereids=Yes 3) 拆解 Nereids Translate / Finalize Scan Node / Create Scan Range 耗时

### case-003: CPU 使用率飙升（Inverted Index 重建）

- **Jira**: [CIR-20954] 【海外-armakuni】CPU使用率飙升
- **标签**: `CPU压力大`, `ai_known_issue`, `海外`
- **Symptom**: 无查询无导入时所有 BE CPU 100%
- **Root cause**: 历史数据有 Inverted Index，Doris 2.1 → 3.0 升级后复合倒排索引格式不兼容，BE 启动后所有 tablet 重建索引，`FSWriteTime` 和 `CompressTime` 占比极高
- **Fix**: 新版本跳过不兼容的复合索引重建；临时方案 `set disable_auto_compaction = true`，等待重建完成
- **Evidence**: be/log `begin to write inverted index`，CPU profile `FSWriteTime + CompressTime > 80%`
- **关键诊断动作**: 1) `top -H` 确认 CPU 消耗在 compaction 线程 2) be/log 搜索 `inverted index` 和 `write` 3) `SHOW PROC '/backends'` 确认 `CompactionScore` 与 base/cumu 无关

### case-004: Overwrite 报错分区冲突

- **Jira**: [CIR-20913] [瑶池][4.0.4] overwrite报错分区冲突
- **标签**: `ai_known_issue`, `insert_over_write`, `存储小组`, `导入`
- **Symptom**: INSERT OVERWRITE 分区报错 "partitions conflict"，该分区不在 WHERE 条件中但被覆盖
- **Root cause**: 用户 SQL `INSERT OVERWRITE t PARTITION(p1) SELECT ... WHERE p2=...` → 代码从 PARTITION 子句取了 p1 但 WHERE 条件匹配到 p2，分区不一致触发 conflict
- **Fix**: 统一分区来源（只用 PARTITION 子句或只用 WHERE 条件），4.0.5+ 修复
- **关键诊断动作**: 1) 确认 SQL 中的分区来源 2) EXPLAIN 确认实际扫描/写入分区

### case-005: 查询结果跳变（tablet 统计信息异常）

- **Jira**: [CIR-20965] 【易生支付】【2.1.7】查询结果出现跳变
- **标签**: `ai_known_issue`
- **Symptom**: 同一查询多次执行返回不同结果
- **Root cause**: tablet 统计信息不正确，CBO 在不同执行间选了不同的 scan 路径
- **关键诊断动作**: 1) EXPLAIN 对比两次执行的 plan 2) `ADMIN CHECK TABLET` 检查数据完整性

---

## Import（导入诊断）

### case-002: Stream Load HTTP 307 重定向失败

- **Jira**: [CIR-20885] [瑶池][4.0.8] Stream Load HTTP/1.1 307 Temporary Redirect 报错
- **标签**: `ai_known_issue`, `streamload`, `导入`
- **Symptom**: Stream Load 返回 `HTTP/1.1 307 Temporary Redirect`，Location header 指向的 BE 不可达
- **Root cause**: FE 返回的 redirect BE 地址使用了内网 IP，客户端在外网。FE `enable_redirect_strict_check=false` 未生效
- **Fix**: FE 配置 `enable_redirect_strict_check = false` + 确保 FE 返回的 BE IP 客户端可达
- **关键诊断动作**: 1) curl -v 查看 307 Location header 2) 确认客户端是否可达该 IP 3) `SHOW BACKENDS` 确认 BE IP

### case-003: INSERT INTO job 不清理导致 FE 内存打爆

- **Jira**: [CIR-20922] [瑶池][26.0.3] insert job任务不清理，fe内存被打爆
- **标签**: `FE`, `INSERTINTO`, `OOM`, `ai_known_issue`, `导入`
- **Severity**: Highest
- **Symptom**: FE 内存持续增长直至 OOM
- **Root cause**: INSERT INTO 的 job 标记为 FINISHED 后 `JobManager` 未从内存中清理，FE restart 后会 reload 所有历史 job，累积数千个 INSERT job → OOM
- **Fix**: FE 代码改进 job 清理逻辑
- **关键诊断动作**: 1) `SHOW LOAD` 和 `SHOW INSERT` 确认历史 job 数量 2) `jmap -histo` 确认 InsertJob 对象堆积

### case-004: Broker Load S3 慢

- **Jira**: [CIR-20898] [26.0.3][BYOC] xero s3_load任务慢
- **标签**: `ai_known_issue`, `brokerload`, `导入`
- **Severity**: High
- **Symptom**: Broker Load 从 S3 导入耗时远超预期
- **Root cause**: S3 prefix 下文件数过多，list 操作耗时远超下载；BE S3 连接数配置过小
- **Fix**: 增加 `s3_max_connections`，使用多文件合并导入
- **关键诊断动作**: 1) S3 list 操作耗时 2) BE log 中 `s3` 相关耗时 3) `s3_max_connections` 配置

---

## Compaction（合并诊断）

### case-002: Schema Change 残留导致 Base Score 高

- **Jira**: [CIR-20876] selectdb-bp17gj52sd1 因为SC残留导致base score高
- **标签**: `ai_known_issue`, `cloud`, `compaction`, `schema-change`
- **Symptom**: base compaction score 长期偏高（max 1490, avg 1370），cumu score 正常（max 79）
- **Root cause**: Schema Change 操作创建了大量 base compaction tablet，但没有清理 SC 上下文，导致 base compaction 调度被阻塞——不是缺少候选 tablet，而是候选 tablet 存在但 `tablet_state` 或 SC 状态不让执行
- **Evidence**: `get_topn_compaction_score ... type=1` 日志显示 base score 高但无对应 compaction 提交
- **Fix**: 清理残留 SC 上下文 + 检查 compaction 过滤条件
- **关键诊断动作**: 1) 区分 base vs cumu score（`type=1` = base, `type=2` = cumu）2) `SHOW ALTER TABLE` 检查 SC 状态 3) be/log `get_topn_tablets_to_compact` 过滤逻辑

### case-003: Cumu Compaction Segfault

- **Jira**: [CIR-20754] 【SF】【2.1.10】cumu compaction报 Segmentation fault
- **标签**: `ai_known_issue`, `compaction`, `存储小组`
- **Symptom**: BE 在执行 cumulative compaction 时 crash (SIGSEGV)
- **Root cause**: 特定 rowset 合并场景下 segment 元数据读取越界 → 空指针访问
- **Fix**: 修复 rowset reader 边界检查（patch 已合入）
- **关键诊断动作**: 1) `dmesg` 确认 core dump 2) GDB backtrace 定位到 `compaction.cpp:XXX` 3) 找到触发 tablet -> 提取 rowset 列表 -> 重放

### case-004: Versions Already Compacted

- **Jira**: [CIR-20721] 【海外-hubspot】compaction失败，[E-230]versions are already compacted
- **标签**: `ai_new_issue`, `compaction`, `gavin处理`, `存储小组`
- **Severity**: High
- **Symptom**: compaction 提交时报 `[E-230]versions are already compacted, version_range=[X-Y]`
- **Root cause**: 多个 compaction 任务竞争同一 tablet，一个提交后另一个版本范围已经不存在但仍在尝试提交
- **Fix**: 改进 compaction 并发控制，提交前二次检查版本范围有效性
- **关键诊断动作**: 1) be/log 搜索 `already compacted` 2) `SHOW TABLET <id>` 确认版本列表 3) 检查 compaction 任务调度重叠

---

## Node（节点健康诊断）

### case-002: Auto Analyze 导致 OOM

- **Jira**: [CIR-20950] 【海外-leetify】auto_analyze导致节点OOM
- **标签**: `ai_new_issue`, `内存`, `海外`
- **Symptom**: `auto_analyze` 开启后 BE 内存持续增长直至 OOM kill
- **Root cause**: auto_analyze 对全表扫描收集统计信息时未受 `mem_limit` 约束，扫描数据量超过可用内存
- **Fix**: 限制 auto_analyze 采样大小 + 增加 mem_limit 保护
- **关键诊断动作**: 1) be/log `MemTrackerLimiter` 确认哪个 operator 超限 2) `SHOW ANALYZE STATUS` 确认正在执行的 analyze 3) 检查 `auto_analyze_table_sample_percent`

### case-003: 单节点内存泄漏（file_cache）

- **Jira**: [CIR-20489] 【瑶池】多节点集群中单节点内存快速上升，疑似内存泄漏
- **标签**: `ai_known_issue`, `file_cache`, `内存泄漏`, `存算分离`
- **Severity**: High
- **Symptom**: cloud 模式下单个节点内存持续上升，无查询时也不释放
- **Root cause**: file_cache 的 LRU 淘汰逻辑在特定条件下失效——cache 命中率高时不会释放旧条目，导致 RSS 持续增长
- **Fix**: 修复 file_cache LRU evict 逻辑 + 设置 `file_cache_query_limit` 上限
- **关键诊断动作**: 1) `be-metrics --grep file_cache` 2) RSS vs MemTracker 差距 3) `jeprof` 确认分配热点

### case-004: FE BDBJE 损坏导致无法启动

- **Jira**: [CIR-19762] bdbje .jdb file not found
- **标签**: `FE`, `FE挂`, `bdbje`, `cloud`, `严重`
- **Severity**: Highest
- **Symptom**: FE 启动失败，`java.io.FileNotFoundException: doris-meta/bdb/0000014d.jdb`
- **Root cause**: BDBJE 日志文件损坏/丢失，可能是磁盘满或异常关机
- **Fix**: 从健康的 Follower/Observer 复制 doris-meta/；如果是 Master 且无其他副本 → BDBJE recovery 工具
- **关键诊断动作**: 1) `ls -la fe/doris-meta/bdb/` 确认文件完整性 2) `SHOW FRONTENDS` 确认是否有健康节点 3) 从健康节点 `rsync` metadta

### case-005: BE 启动即占用 200GB 内存

- **Jira**: [CIR-19666] 【观测云】【2.1.7】BE一启动就占用200GB的内存
- **标签**: `内存`, `查询执行小组`
- **Symptom**: BE 刚启动，无查询，RSS 200GB+
- **Root cause**: `mem_limit=80%` 但 `storage_page_cache_limit` 等缓存配置未显式设置，BE 默认分配大量 page cache
- **Fix**: 显式设置 `storage_page_cache_limit` 和 `max_segment_cache_size`
- **关键诊断动作**: 1) `ps aux` 确认 RSS vs mem_limit 2) `be-metrics --grep cache` 3) 检查 be.conf 缓存相关配置

---

## Tablet（Tablet/副本诊断）

### case-001: Tablet 统计信息异常

- **Jira**: [CIR-20952] 【海外-暂未知用户】tablet的统计信息不正常
- **标签**: `ai_pending_judgment`, `存储小组`, `海外`
- **Symptom**: `SHOW TABLET` 或 `SHOW DATA` 显示的 tablet 大小/行数与实际不符
- **关键诊断动作**: 1) `SHOW TABLET <id>` 2) `ADMIN DIAGNOSE TABLET <id>` 3) `SHOW PROC '/statistic'`

### case-002: S3 冷热分层数据未及时清理

- **Jira**: [CIR-20838] 【观测云-浦江数链】【2.1.7】S3上数据未被及时清理
- **标签**: `ai_new_issue`, `冷热分离`, `存储小组`
- **Severity**: High
- **Symptom**: cooldown 到 S3 的数据在 S3 侧没有被清理，存储成本持续增长
- **Root cause**: 冷热分层 cooldown 策略只迁移数据不删除，expired 清理任务被后台调度延迟；22 条评论中有详细的分析链
- **关键诊断动作**: 1) `SHOW EXPIRED POLICY` 2) S3 listing 对比本地 tablet 3) `SHOW PROC '/trash'` 确认回收站

---

## Deployment（部署诊断）

### case-001: FE NPE 无法启动

- **Jira**: [CIR-20933] 【海外-暂未知用户】FE报错NPE导致无法启动
- **标签**: `FE`, `FE挂`, `ai_new_issue`, `海外`
- **Symptom**: FE 启动时 `NullPointerException`，无法完成 bootstrap
- **关键诊断动作**: 1) `fe.log` 完整 stacktrace 2) `fe/doris-meta/image/` 最新 image 文件完整性 3) `fe.conf` 配置变更历史

---

## Data Lake（数据湖诊断）

### case-001: Glue Catalog 无法展示 Database

- **Jira**: [CIR-20756] 【海外-ADIA】无法正确展示glue catalog下的database
- **标签**: `ai_pending_judgment`, `glue`, `数据湖`, `海外`
- **Symptom**: `SHOW DATABASES FROM glue_catalog` 只返回部分 database
- **Root cause**: Glue API pagination 未正确处理 `NextToken`，超过第一页的 database 丢失
- **Fix**: 修复 Glue catalog 的 `getAllDatabases` 分页逻辑
- **关键诊断动作**: 1) `SHOW CATALOGS` + `SHOW DATABASES` 2) fe.log 搜索 `GlueCatalog` 错误 3) AWS Glue API 直接调用对比结果

### case-002: Iceberg 分区表无法识别

- **Jira**: [CIR-20700] 【海外-ADIA】doris无法识别iceberg分区表
- **标签**: `ai_new_issue`, `iceberg`, `数据湖`, `海外`
- **Severity**: High
- **Symptom**: `SHOW PARTITIONS FROM iceberg_catalog.db.tbl` 返回空
- **Root cause**: Iceberg 表使用 `identity` 分区变换 + `year/month/day` 等 temporal transforms，Doris 只支持 `identity` 和 `bucket`
- **Fix**: 增加 temporal partition transform 支持
- **关键诊断动作**: 1) `SHOW CREATE TABLE` (Iceberg side) 确认 `partitioning` 2) fe.log 搜索 `IcebergTable`

---

## Resource Isolation（资源隔离诊断）

### case-001: Spill Disk 测试不符合预期

- **Jira**: [CIR-20961] 【C项目】spill disk 测试不符合预期
- **标签**: `SAAS`, `ai_new_issue`, `spill`
- **Severity**: High
- **Symptom**: 开启 `enable_spill` 后查询仍然 OOM，spill 未生效
- **Root cause**: spill 只对特定 operator（agg/join）生效；spill 触发阈值与 mem_limit 的关系不明确
- **关键诊断动作**: 1) `SET enable_spill=true` 2) Profile `SpillDataSize` > 0 确认 spill 触发 3) `be-metrics --grep spill`

### case-002: MEM_LIMIT_EXCEEDED 但 sys available memory 不准

- **Jira**: [CIR-20430] 【瑶池】导入触发 MEM_LIMIT_EXCEEDED，sys available memory 统计不准确
- **标签**: `查询执行小组`
- **Severity**: High
- **Symptom**: `mem_limit` 设置为 80% 系统内存，但导入仍然报 MEM_LIMIT_EXCEEDED，实际 `free` 显示还有大量可用内存
- **Root cause**: `/proc/meminfo` `MemAvailable` 的值在 cgroup 容器中不准确，Doris 读取的 "available memory" 包含了可回收的 page cache
- **Fix**: 改用 cgroup `memory.limit_in_bytes - memory.usage_in_bytes` 作为可用内存计算源
- **关键诊断动作**: 1) `free -h` vs `cat /sys/fs/cgroup/memory/memory.limit_in_bytes` 2) be/log 确认 MemTrackerLimiter 的实际触发值 3) `be-metrics --grep memory`

---

## Cloud Diagnoses（存算分离诊断）

### case-001: 查询卡住，Plan 竞态（慢 plan 反而被选中）

- **Jira**: [CIR-20893] [cloud][26.0.4][AWHKDKHC] 查询卡住，慢的查询plan比快的更优
- **标签**: `ai_new_issue`, `cloud`
- **Severity**: High
- **Symptom**: 同一查询时而毫秒返回、时而卡住数分钟；EXPLAIN 显示卡住的执行选了慢的 plan
- **Root cause**: CBO cost estimation 在 cloud 模式下与实际执行成本不一致——S3 IO 延迟的不确定性加上 plan caching race
- **关键诊断动作**: 1) EXPLAIN 对比快慢执行 2) `SET enable_plan_cache = false` 验证 3) Profile 对比

### case-002: BE 资源不释放但无查询运行

- **Jira**: [CIR-20940] [byoc][4.0.11] be资源不释放，但是上面没有查询在跑
- **标签**: `ai_pending_judgment`, `cloud`
- **Severity**: High
- **Symptom**: BE RSS 持续 %mem_limit，但 `SHOW PROC '/current_queries'` 为空
- **Root cause**: 之前的查询 fragment 已结束但 brpc channel 未释放 + file_cache 未 evict
- **Fix**: 周期性 `reset_rpc_channel` + 缩短 file_cache TTL
- **关键诊断动作**: 1) `SHOW PROC '/current_queries'` 2) `be-metrics --grep fragment` 3) `be-metrics --grep file_cache` 4) RSS vs MemTracker

---

## 使用方式

在 doris-debug skill 中引用本文档的案例：

```markdown
## Related CIR cases
- [CIR-20967] Plan Time 超长 — Nereids Iceberg scan range 创建阶段 RPC 爆炸 → `references/03-cir-case-index.md#case-002-fe-nereids-plan-time-超长`
```

每个 skill 的 case 文件应引用至少一个 CIR 真实案例作为背景。
