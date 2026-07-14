# CIR Case Index（Jira 生产案例 → Skill 映射）

> 数据来源：Jira CIR 项目 (http://jira.selectdb-in.cc/)，共计 20,000+ issue，筛选 43 个代表性案例。
> 本文档按 doris-debug skill 分类，每个案例含 Symptom / Root cause / Fix / 关键诊断动作。

## 统计概览

| 诊断域 | 案例数 | 关键模式 |
|--------|--------|----------|
| Query | 7 | Plan Time / Scan 瓶颈 / Exchange E11 / 结果跳变 / Overwrite 冲突 / CPU 异常 / 计算组差异 |
| Import | 6 | 307 重定向 / FE OOM 泄露 / S3 load 慢 / RPC timeout / Arrow 格式 / meta-service 慢 |
| Compaction | 5 | SC 残留 base score / cumu segfault / 版本 compacted / cumu score 高 / inverted index 重建 |
| Node | 7 | Auto analyze OOM / file_cache 泄漏 / BE coredump / FE bdbje 损坏 / BE 内存持续泄漏 / CPU 异常 / 启动 200GB |
| Tablet | 3 | 统计异常 / S3 冷热分离 / 写入超时 |
| Deployment | 2 | FE NPE 启动 / BE 配置无法启动 |
| Data Lake | 5 | Glue pagination / Iceberg 分区表 / Plan Time Iceberg / 谓词下推缺失 / 老挝银行 View struct |
| Resource Isolation | 5 | Spill disk / cgroup memory / Workload policy CME / Compute group 差异 / WG 绑定 |
| Cloud | 5 | Plan 竞态 / BE 资源不释放 / Warmup cache miss / File cache 内存泄漏 / FDB 堆积 |

---

## Query（查询诊断）— 7 个案例

### Case Q1: FE Nereids Plan Time 10min（Iceberg 外表 RPC 爆炸）

- **Jira**: [CIR-20967] 【海外-spinny】plan time超长  
- **标签**: `ai_new_issue`, `海外` | 14 comments
- **Severity**: Medium
- **Symptom**: 查询总耗时 10min8s，`Plan Time=10min8sec`，BE 实际执行只有 214ms/1MB 数据
- **Root cause**: Nereids `Finalize Scan Node → Create Scan Range` 阶段每次 `getManifestFiles` 调用 `UpdateRunningStatus` 触发 `msClient.updateInstance` RPC，64 文件 × 63 分区反复调用，每次 ~200ms → 10min+
- **Fix**: 短期：调大 `iceberg_manifest_cache_refresh_interval_s`；长期：改进 scan range 创建减少重复 RPC
- **Evidence**: Profile `Create Scan Range Time=10min1sec`, `Get Splits Time=6sec`, `Is Nereids=Yes`
- **关键诊断动作**: Profile → Plan Time 占比 → 拆解 Nereids Translate / Finalize Scan Node / Create Scan Range

### Case Q2: CPU 使用率飙升（Inverted Index 重建）

- **Jira**: [CIR-20954] 【海外-armakuni】CPU使用率飙升  
- **标签**: `CPU压力大`, `ai_known_issue`, `海外` | 4 comments
- **Severity**: Medium
- **Symptom**: 无查询无导入时所有 BE CPU 100%
- **Root cause**: Doris 2.1→3.0 升级后复合倒排索引格式不兼容，BE 启动后对所有 tablet 重建索引
- **Fix**: 新版本跳过不兼容的复合索引重建；临时 `SET disable_auto_compaction = true`
- **Evidence**: be/log `begin to write inverted index`, CPU profile `FSWriteTime + CompressTime > 80%`
- **关键诊断动作**: `top -H` → be/log `inverted index` → `SHOW PROC '/backends'` CompactionScore

### Case Q3: [E11] Resource temporarily unavailable（Exchange brpc fanout）

- **Jira**: [CIR-20928] [瑶池][4.0.7] 查询报错 Resource temporarily unavailable
- **标签**: `ai_known_issue`, `瑶池` | 8 comments | **Priority: High**
- **Severity**: High
- **Symptom**: 高峰期查询报 `failed to send brpc when exchange, error=[E11]Resource temporarily unavailable`
- **Root cause**: `parallel_exchange_instance_num=100` 在高并发/高 fanout 查询下 exchange RPC 发送侧打到 EAGAIN，brpc socket 发送队列满
- **Fix**: 调小 `parallel_exchange_instance_num`；长期 backport apache/doris PR #50113 (one rpc send multi blocks)
- **Evidence**: be/log `RPC meet failed: [E11]`、`failed to send brpc when exchange @<target-be>:8060`
- **关键诊断动作**: 1) 区分 E11 brpc vs pthread_create EAGAIN（后者才是线程池打满）2) 统计目标 BE 分布（单点 vs 全集群）3) 确认 `parallel_exchange_instance_num` 配置

### Case Q4: 同一查询在不同计算组耗时差异大（Scan Open/Init 阶段）

- **Jira**: [CIR-20924] [瑶池][4.0.8] 同一个查询在不同的计算组查询耗时差异大
- **标签**: `ai_known_issue`, `瑶池` | 10 comments
- **Severity**: Medium
- **Symptom**: 同一 SQL 在快组 284ms，慢组 3sec257ms，两边 rows/bytes 相同（均返回 0 行）
- **Root cause**: 慢计算组的 OLAP scan `OpenTime=2sec647ms`，在真正读数据前需要同步更多远端 rowset metadata / delete bitmap（cloud 模式同步开销）
- **Evidence**: 慢 Profile `ScannerInitTime=2sec647ms`, 快 Profile `ScannerInitTime=<1ms`
- **关键诊断动作**: 1) Profile 对比 scan open/init 阶段 2) 确认 ScannerInitTime/OpenTime 差异 3) 检查计算组缓存状态

### Case Q5: Overwrite 报错分区冲突

- **Jira**: [CIR-20913] [瑶池][4.0.4] overwrite报错分区冲突
- **标签**: `ai_known_issue`, `insert_over_write` | 7 comments | **Priority: High**
- **Severity**: High
- **Symptom**: INSERT OVERWRITE t PARTITION(p1) SELECT ... WHERE p2=... → "partitions conflict"
- **Root cause**: PARTITION 子句取 p1 但 WHERE 条件匹配到 p2，代码未统一分区来源
- **Fix**: 统一分区来源（只用 PARTITION 子句或只用 WHERE 条件），4.0.5+ 修复
- **关键诊断动作**: EXPLAIN 确认实际扫描/写入分区 → 对比 PARTITION 子句 vs WHERE 条件

### Case Q6: 查询结果跳变

- **Jira**: [CIR-20965] 【易生支付】【2.1.7】查询结果出现跳变
- **标签**: `ai_known_issue` | 3 comments
- **Severity**: Medium
- **Symptom**: 同一查询多次执行返回不同结果
- **Root cause**: tablet 统计信息不正确，CBO 在不同执行间选了不同的 scan 路径
- **关键诊断动作**: EXPLAIN 对比两次 plan → `ADMIN CHECK TABLET`

### Case Q7: Match Phrase vs Like 结果不一致

- **Jira**: [CIR-20937] 【中原消费金融】【2.1.12】match_phrase_prefix 和 like 查询结果不一样
- **标签**: `ai_known_issue` | 8 comments
- **Severity**: Medium
- **Symptom**: `MATCH_PHRASE_PREFIX('xx')` 和 `LIKE 'xx%'` 对相同数据返回不同结果
- **Root cause**: Inverted Index 分词器与 LIKE 的字符匹配语义差异
- **关键诊断动作**: 1) EXPLAIN 确认是否命中 inverted index 2) `SHOW INDEX` 确认索引定义

---

## Import（导入诊断）— 6 个案例

### Case I1: Stream Load HTTP 307 重定向失败

- **Jira**: [CIR-20885] [瑶池][4.0.8] Stream Load HTTP/1.1 307 Temporary Redirect 报错
- **标签**: `ai_known_issue`, `streamload`, `导入` | 6 comments | **Priority: High**
- **Severity**: High
- **Symptom**: Stream Load 返回 307，Location header 指向的 BE IP 客户端不可达
- **Root cause**: FE 返回 redirect BE 内网 IP，客户端在外网
- **Fix**: `enable_redirect_strict_check = false` + 确保 BE IP 客户端可达
- **关键诊断动作**: `curl -v` 查看 307 Location → 确认 IP 可达性 → `SHOW BACKENDS`

### Case I2: INSERT INTO job 不清理 → FE OOM

- **Jira**: [CIR-20922] [瑶池][26.0.3] insert job任务不清理，fe内存被打爆
- **标签**: `FE`, `INSERTINTO`, `OOM`, `ai_known_issue`, `导入` | 8 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: FE 内存持续增长直至 OOM，重启后 reload 历史 INSERT job 再次 OOM
- **Root cause**: INSERT INTO job 标记 FINISHED 后 `JobManager` 未清理，累积数千个 job
- **Fix**: FE 代码改进 job 清理；临时 `jmap -histo` 确认 InsertJob 堆积
- **关键诊断动作**: `SHOW LOAD` / `SHOW INSERT` → `jmap -histo` → `jmap -dump:live`

### Case I3: Broker Load S3 list 慢

- **Jira**: [CIR-20898] [26.0.3][BYOC] xero s3_load任务慢
- **标签**: `ai_known_issue`, `brokerload`, `导入` | 7 comments | **Priority: High**
- **Severity**: High
- **Symptom**: Broker Load 从 S3 导入耗时远超预期，list 操作耗时 > 下载
- **Root cause**: S3 prefix 文件数过多 + `s3_max_connections` 过小
- **Fix**: 增加 `s3_max_connections`，合并小文件后再导入
- **关键诊断动作**: S3 list 耗时 → BE log s3 → `s3_max_connections`

### Case I4: 导入 RPC timed out（heavy work pool 打满）

- **Jira**: [CIR-20891] [BYOC][4.0.9][AWOR8A0P] 导入 failed to open tablet writer, RPC call timed out
- **标签**: `BYOC`, `ai_pending_judgment` | 14 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: 导入 open tablet writer 阶段等待目标 BE 返回 RPC 超过 60s，随后 coordinator cancel 整条 load
- **Root cause**: 目标 BE `brpc_heavy` work pool 在该时段被打满/卡住，`tablet_writer_open` 进入 heavy pool 后执行过慢或排队超时
- **Code path**: `VNodeChannel::_open_internal` → `PBackendService_Stub::tablet_writer_open(timeout=60s)` → `PInternalService::tablet_writer_open` → `_heavy_work_pool.try_offer`
- **Fix**: 短期降低/错峰 load 并发；中期 `brpc_heavy_work_pool_threads 256→384`；故障时保留 pstack 再重启
- **关键诊断动作**: 1) be/log `RPC call is timed out` 目标 BE 2) 确认同一窗口是否成簇出现 3) 检查 `fail to offer request to the work pool` 签名 4) pstack 卡点

### Case I5: Arrow 格式 Stream Load 报错

- **Jira**: [CIR-20795] arrow 格式数据通过streamload导入报错
- **标签**: `ai_new_issue` | 4 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: Arrow 格式 Stream Load 报 schema 解析错误
- **Root cause**: Arrow IPC 格式与 Doris 预期的 Arrow schema 字段类型映射不一致
- **关键诊断动作**: Arrow schema 验证 → BE log arrow → 对比支持的 Arrow 类型映射

### Case I6: meta-service 导致导入慢

- **Jira**: [CIR-20856] [AWVASN8A] 用户导入慢
- **标签**: `ai_new_issue`, `fdb`, `meta-service`, `导入` | 4 comments | **Priority: High**
- **Severity**: High
- **Symptom**: 导入耗时显著增长，与数据量不成比例
- **Root cause**: meta-service (FDB) 在导入 publish 阶段延迟高
- **关键诊断动作**: fe.log publish 阶段耗时 → meta-service latency 监控

---

## Compaction（合并诊断）— 5 个案例

### Case C1: Schema Change 残留 → Base Score 高

- **Jira**: [CIR-20876] selectdb-bp17gj52sd1 因为SC残留导致base score高
- **标签**: `ai_known_issue`, `cloud`, `compaction`, `schema-change` | 15 comments
- **Severity**: Medium
- **Symptom**: base compaction score max 1490 / avg 1370，cumu score 正常 (max 79)
- **Root cause**: SC 操作创建大量 base compaction tablet 但不清理 SC 上下文，`tablet_state` 或 SC 状态阻止执行
- **Evidence**: `get_topn_compaction_score ... type=1` → score 高，但 `type=2` 正常
- **Fix**: 清理残留 SC 上下文 + 检查 compaction 过滤条件
- **关键诊断动作**: 区分 base(type=1) vs cumu(type=2) → `SHOW ALTER TABLE` → be/log 过滤逻辑

### Case C2: Cumu Compaction Segfault

- **Jira**: [CIR-20754] 【SF】【2.1.10】cumu compaction报 Segmentation fault
- **标签**: `ai_known_issue`, `compaction`, `存储小组` | 10 comments
- **Severity**: Medium
- **Symptom**: BE 执行 cumulative compaction 时 SIGSEGV core dump
- **Root cause**: 特定 rowset 合并场景下 segment 元数据读取越界 → 空指针
- **Fix**: 修复 rowset reader 边界检查（patch 已合入）
- **关键诊断动作**: `dmesg` → GDB backtrace `compaction.cpp:XXX` → 提取触发 tablet → rowset 列表

### Case C3: Versions Already Compacted（compaction 竞态）

- **Jira**: [CIR-20721] 【海外-hubspot】compaction失败，[E-230]versions are already compacted
- **标签**: `ai_new_issue`, `compaction`, `存储小组` | 9 comments | **Priority: High**
- **Severity**: High
- **Symptom**: compaction 提交报 `[E-230]versions are already compacted, version_range=[X-Y]`
- **Root cause**: 多个 compaction 任务竞争同一 tablet，提交时另一任务已处理相同版本范围
- **Fix**: 提交前二次检查版本范围有效性
- **关键诊断动作**: be/log `already compacted` → `SHOW TABLET <id>` 版本列表 → 任务调度重叠检查

### Case C4: Cumu Score 高但 Base 正常

- **Jira**: [CIR-20855] selectdb-cn-9y34ud5kz01 cumu score 高
- **标签**: `ai_known_issue`, `cloud`, `compaction`, `瑶池` | 12 comments
- **Severity**: Medium
- **Symptom**: cumu score 持续升高，base score 正常
- **Root cause**: 高频写入产生大量 cumulative point，cumu compaction 吞吐不足
- **Fix**: 调大 `max_cumulative_compaction_threads`、`compaction_task_num_per_disk`
- **关键诊断动作**: `be-metrics --grep compaction`→ `iostat -x 1` 磁盘 IO → 对比 base vs cumu score

### Case C5: Base Score 高但找不到对应 Tablet

- **Jira**: [CIR-20650] [瑶池][3.0.10] be base compaction score 高但是没找到高的 tablet
- **标签**: `ai_pending_judgment`, `compaction`, `存算分离` | 5 comments
- **Severity**: Medium
- **Symptom**: Grafana base score 告警高，但 `get_topn_tablets_to_compact()` 没有高分 tablet
- **Root cause**: cloud 调度更新了 `tablet_base_max_compaction_score` 指标但不 pick tablet（slot/状态/过滤条件不满足）
- **关键诊断动作**: 区分 "score 更新但未调度" vs "有候选但不允许执行" → 检查 slot 和过滤条件

---

## Node（节点健康诊断）— 7 个案例

### Case N1: Auto Analyze → OOM

- **Jira**: [CIR-20950] 【海外-leetify】auto_analyze导致节点OOM
- **标签**: `ai_new_issue`, `内存`, `海外` | 2 comments
- **Severity**: Medium
- **Symptom**: `auto_analyze` 开启后 BE OOM kill
- **Root cause**: auto_analyze 全表扫描收集统计信息时不受 `mem_limit` 约束
- **Fix**: 限制 `auto_analyze_table_sample_percent` + mem_limit 保护
- **关键诊断动作**: be/log MemTrackerLimiter → `SHOW ANALYZE STATUS`

### Case N2: File Cache 内存泄漏

- **Jira**: [CIR-20870] [瑶池][4.1.2] file cache BE 内存泄露
- **标签**: `ai_known_issue`, `file_cache`, `内存泄漏`, `瑶池` | 13 comments | **Priority: High**
- **Severity**: High
- **Symptom**: BE RSS 持续增长，无查询也不释放，file_cache 占用持续增长
- **Root cause**: file_cache LRU evict 在高命中率时失效
- **Fix**: 修复 LRU evict + 设置 `file_cache_query_limit`
- **关键诊断动作**: `be-metrics --grep file_cache` → RSS vs MemTracker → `jeprof`

### Case N3: BE 持续 Coredump

- **Jira**: [CIR-20906] [瑶池][4.0.4] be持续coredump
- **标签**: `ai_pending_judgment`, `瑶池` | 7 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: 同一 BE 反复 core dump 重启
- **Root cause**: 特定查询/导入触发 segment reader 内存越界或 use-after-free
- **关键诊断动作**: `dmesg` / `coredumpctl` → GDB backtrace → 提取 query_id / load_id → 回放触发

### Case N4: FE BDBJE 损坏

- **Jira**: [CIR-19762] bdbje .jdb file not found
- **标签**: `FE`, `FE挂`, `bdbje`, `cloud`, `严重` | 4 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: FE 启动 `java.io.FileNotFoundException: doris-meta/bdb/0000014d.jdb`
- **Root cause**: BDBJE 日志文件损坏/丢失（磁盘满或异常关机）
- **Fix**: 从健康 Follower/Observer rsync doris-meta；Master 无副本 → BDBJE recovery 工具
- **关键诊断动作**: `ls fe/doris-meta/bdb/` → `SHOW FRONTENDS` → rsync

### Case N5: 单台 BE 内存持续泄漏 + CPU 异常

- **Jira**: [CIR-20941] [byoc][4.1.3][HWSHL0S7] 深大智能，单台BE内存持续泄漏，CPU出现异常
- **标签**: `ai_pending_judgment` | 16 comments | **Priority: High**
- **Severity**: High
- **Symptom**: 单 BE RSS 持续线性增长 + CPU 也随之升高，其他 BE 正常
- **Root cause**: 疑似特定查询的 fragment 未释放 + 持续重试；cpu 异常是内存回收压力导致
- **关键诊断动作**: `jeprof` 分配热点 → `SHOW PROC '/current_queries'` → be/log MemTracker → 隔离节点对比

### Case N6: BE 启动即占 200GB 内存

- **Jira**: [CIR-19666] 【观测云】【2.1.7】BE一启动就占用200GB的内存
- **标签**: `内存` | 5 comments
- **Severity**: Medium
- **Symptom**: BE 刚启动，无查询，RSS 200GB+
- **Root cause**: `mem_limit=80%` 但 `storage_page_cache_limit` 等未显式设置，默认分配大量 page cache
- **Fix**: 显式设置 `storage_page_cache_limit` + `max_segment_cache_size`
- **关键诊断动作**: RSS vs mem_limit → `be-metrics --grep cache` → be.conf 缓存配置

### Case N7: 内存疑似泄漏（特定版本 YCSB 场景）

- **Jira**: [CIR-20854] [瑶池][4.1.7] 内存疑似泄漏
- **标签**: `ai_new_issue`, `瑶池` | 8 comments
- **Severity**: Medium
- **Symptom**: YCSB 压测场景下 BE 内存持续上升不回落
- **Root cause**: YCSB 高频短查询产生的 fragment context 回收不及时
- **关键诊断动作**: `jeprof --inuse_space` → 对比压测前后 → fragment 对象计数

---

## Tablet（Tablet/副本诊断）— 3 个案例

### Case T1: Tablet 统计信息异常

- **Jira**: [CIR-20952] 【海外-暂未知用户】tablet的统计信息不正常
- **标签**: `ai_pending_judgment`, `存储小组`, `海外`
- **Severity**: Medium
- **Symptom**: `SHOW TABLET` / `SHOW DATA` 显示的 tablet 大小/行数与实际不符
- **关键诊断动作**: `SHOW TABLET <id>` → `ADMIN DIAGNOSE TABLET <id>` → `SHOW PROC '/statistic'`

### Case T2: S3 冷热分层数据未清理

- **Jira**: [CIR-20838] 【观测云-浦江数链】【2.1.7】S3上数据未被及时清理
- **标签**: `ai_new_issue`, `冷热分离`, `存储小组` | 22 comments | **Priority: High**
- **Severity**: High
- **Symptom**: cooldown 到 S3 的数据在 S3 侧未被删除，存储成本持续增长
- **Root cause**: cooldown 策略只迁移不删除，expired 清理任务被后台调度延迟
- **关键诊断动作**: `SHOW EXPIRED POLICY` → S3 listing vs 本地 tablet → `SHOW PROC '/trash'`

### Case T3: 写入超时 + EPOLLOUT 失败

- **Jira**: [CIR-20757] 【快猫】【3.1.3】写入时间偶尔达到了1分钟 + Fail to wait EPOLLOUT of fd
- **标签**: `ai_pending_judgment`, `存储小组`, `导入` | 7 comments
- **Severity**: Low（但影响写入）
- **Symptom**: 写入偶尔 1 分钟+，日志大量 `Fail to wait EPOLLOUT of fd=XXX: Connection timed out`
- **Root cause**: brpc socket 发送缓冲区满或对端接收慢 → TCP send buffer 拥塞
- **关键诊断动作**: `netstat -s` 重传统计 → TCP send queue 检查 → 对端 BE 负载

---

## Deployment（部署诊断）— 2 个案例

### Case D1: FE NPE 无法启动

- **Jira**: [CIR-20933] 【海外-暂未知用户】FE报错NPE导致无法启动
- **标签**: `FE`, `FE挂`, `ai_new_issue`, `海外` | 4 comments
- **Severity**: Medium
- **Symptom**: FE 启动时 `NullPointerException` 无法完成 bootstrap
- **关键诊断动作**: fe.log stacktrace → `fe/doris-meta/image/` 文件完整性 → fe.conf 变更历史

### Case D2: 新配置 BE 无法启动

- **Jira**: [CIR-20908] 【杭银消金】【2.1.8】新配置BE无法启动
- **标签**: `ai_known_issue` | 8 comments
- **Severity**: Medium
- **Symptom**: 新加入集群的 BE 启动失败
- **Root cause**: BE 配置中的 `storage_root_path` 权限/路径问题或 `priority_networks` 绑定失败
- **关键诊断动作**: be.out 启动日志 → 端口占用 `fuser` → `priority_networks` 配置 → 目录权限

---

## Data Lake（数据湖诊断）— 5 个案例

### Case DL1: Glue Catalog Pagination 丢失 Database

- **Jira**: [CIR-20756] 【海外-ADIA】无法正确展示glue catalog下的database
- **标签**: `ai_pending_judgment`, `glue`, `数据湖`, `海外` | 7 comments
- **Severity**: Medium
- **Symptom**: `SHOW DATABASES FROM glue_catalog` 只返回部分 database
- **Root cause**: Glue API `getAllDatabases` 未正确处理 `NextToken` pagination
- **Fix**: 修复 pagination 逻辑
- **关键诊断动作**: 对比 Glue API 直接调用 vs Doris SHOW DATABASES → fe.log `GlueCatalog`

### Case DL2: Iceberg 分区表无法识别（Temporal Transforms）

- **Jira**: [CIR-20700] 【海外-ADIA】doris无法识别iceberg分区表
- **标签**: `ai_new_issue`, `iceberg`, `数据湖`, `海外` | 6 comments | **Priority: High**
- **Severity**: High
- **Symptom**: `SHOW PARTITIONS FROM iceberg_catalog.db.tbl` 返回空
- **Root cause**: Iceberg `year/month/day` temporal partition transforms 不被 Doris 支持
- **Fix**: 增加 temporal partition transform 支持
- **关键诊断动作**: Iceberg `SHOW CREATE TABLE` → 确认 `partitioning` → fe.log `IcebergTable`

### Case DL3: Iceberg INSERT 耗时较长

- **Jira**: [CIR-20672] 【海外-safaricom】insert iceberg catalog耗时较长
- **标签**: `ai_pending_judgment`, `iceberg`, `数据湖`, `海外` | 4 comments | **Priority: High**
- **Severity**: High
- **Symptom**: INSERT INTO iceberg_catalog.db.tbl 耗时远超预期
- **Root cause**: Iceberg commit 阶段与 catalog 的多次交互（snapshot/commit/expireSnapshots）
- **关键诊断动作**: Profile INSERT 各阶段耗时 → Iceberg commit metrics → `iceberg_commit_batch_size`

### Case DL4: JDBC 外表与内表 JOIN 无谓词下推

- **Jira**: [CIR-20816] 【海外-老挝银行】jbdc外表与内表join时没有谓词下推
- **标签**: `ai_new_issue`, `jdbc-catalog`, `join`, `海外`, `谓词下推` | 6 comments
- **Severity**: Medium
- **Symptom**: JDBC catalog 外表 JOIN Doris 内表时 WHERE 条件未下推到外表
- **Root cause**: CBO 未识别 JDBC catalog 的谓词下推能力（`push_down_predicates` capability）
- **Fix**: 添加 JDBC catalog 谓词下推适配
- **关键诊断动作**: EXPLAIN VERBOSE → 确认 scan 阶段无 pushdown → fe.log catalog capability

### Case DL5: MV Original Struct Info Invalid

- **Jira**: [CIR-20815] 【海外-老挝银行】explain报错View original struct info is invalid
- **标签**: `ai_new_issue`, `海外`, `物化视图` | 6 comments
- **Severity**: Medium
- **Symptom**: `EXPLAIN SELECT ...` 报 "View original struct info is invalid"
- **Root cause**: MV 定义中引用的基表列已变更（ALTER TABLE DROP/CHANGE COLUMN），MV 元数据未同步
- **关键诊断动作**: `SHOW CREATE MATERIALIZED VIEW` vs `SHOW CREATE TABLE` → 对比列差异

---

## Resource Isolation（资源隔离诊断）— 5 个案例

### Case R1: Spill Disk 不生效

- **Jira**: [CIR-20961] 【C项目】spill disk 测试不符合预期
- **标签**: `SAAS`, `ai_new_issue`, `spill` | 3 comments | **Priority: High**
- **Severity**: High
- **Symptom**: `enable_spill=true` 后查询仍然 OOM
- **Root cause**: spill 只对 agg/join operator 生效；spill 触发阈值与 mem_limit 关系不清
- **关键诊断动作**: Profile `SpillDataSize` → `be-metrics --grep spill` → 确认触发 operator

### Case R2: MEM_LIMIT_EXCEEDED 但系统内存充足（cgroup）

- **Jira**: [CIR-20430] 【瑶池】导入触发 MEM_LIMIT_EXCEEDED，sys available memory 统计不准确
- **标签**: `查询执行小组` | 4 comments | **Priority: High**
- **Severity**: High
- **Symptom**: `mem_limit=80%` 但导入报 MEM_LIMIT_EXCEEDED，`free` 显示还有大量可用内存
- **Root cause**: `/proc/meminfo MemAvailable` 在 cgroup 容器中包含可回收 page cache，值不准确
- **Fix**: 改用 cgroup `memory.limit_in_bytes - memory.usage_in_bytes`
- **关键诊断动作**: `free -h` vs cgroup memory.limit_in_bytes → be/log MemTrackerLimiter → `be-metrics --grep memory`

### Case R3: Workload Policy ConcurrentModificationException

- **Jira**: [CIR-20715] [瑶池][4.1.7] 线上查询偶发报错 java.util.ConcurrentModificationException
- **标签**: `ai_new_issue`, `瑶池` | 14 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: 查询偶发 `java.util.ConcurrentModificationException`，概率低但影响面大
- **Root cause**: Workload Policy 的 query routing 阶段并发修改 policy list（未加锁迭代）
- **Fix**: 加 concurrent collection 或 copy-on-read
- **关键诊断动作**: fe.log stacktrace → 确认 `WorkloadPolicyMgr` 调用栈 → 并发场景重现

### Case R4: 同一个 Workload Group 绑定多个 Compute Group

- **Jira**: [CIR-20800] 【海外-ADIA】同一个workload group绑定多个compute group的使用问题
- **标签**: `compute-group`, `workloadgroup`, `海外` | 4 comments
- **Severity**: Medium
- **Symptom**: 一个 WG 绑定多个 compute group 时，查询路由行为不明确
- **Root cause**: WG-compute group 多对多绑定下，查询分发逻辑未文档化
- **关键诊断动作**: `SHOW WORKLOAD GROUPS` → compute group 绑定关系 → `EXPLAIN` 确认路由

### Case R5: MV Refresh 使用其所有者资源

- **Jira**: [CIR-20801] 【海外-ADIA】刷新物化视图使用其所有者的资源
- **标签**: `ai_known_issue`, `compute-group`, `海外`, `物化视图` | 3 comments
- **Severity**: Medium
- **Symptom**: MTMV refresh 在一个 compute group 执行，但使用创建者的 workload group 资源配额
- **Root cause**: MV refresh 任务继承创建者 session 的 WG，而非目标 compute group 默认 WG
- **关键诊断动作**: `mv_infos()` → refresh 任务 Profile → WG 资源使用对比

---

## Cloud Diagnoses（存算分离诊断）— 5 个案例

### Case CL1: Warmup 后查询仍 Cache Miss

- **Jira**: [CIR-20794] [BYOC][4.0.4.9][ALBJ2NC8] warm up后查询仍cache miss
- **标签**: `BYOC`, `ai_new_issue` | 10 comments | **Priority: Highest**
- **Severity**: Critical
- **Symptom**: 执行 warmup 后查询仍全量从 S3 读取，file_cache 未命中
- **Root cause**: warmup 操作未覆盖所有需要的 segment 文件或 delete bitmap，或 cache TTL 过短
- **Fix**: 确认 warmup 覆盖范围 + 延长 cache TTL
- **关键诊断动作**: `be-metrics --grep file_cache` hit ratio → S3 GET 量对比 → warmup 范围

### Case CL2: BE 资源不释放但无查询运行

- **Jira**: [CIR-20940] [byoc][4.0.11][GCORKXOL] be资源不释放，无查询在跑
- **标签**: `ai_pending_judgment`, `cloud` | 13 comments | **Priority: High**
- **Severity**: High
- **Symptom**: BE RSS 持续 %mem_limit，`SHOW PROC '/current_queries'` 为空
- **Root cause**: 历史查询 fragment 结束但 brpc channel 未释放 + file_cache 未 evict
- **Fix**: `reset_rpc_channel` + 缩短 file_cache TTL
- **关键诊断动作**: `SHOW PROC '/current_queries'` → `be-metrics --grep fragment` → `be-metrics --grep file_cache` → RSS vs MemTracker

### Case CL3: 查询卡住 + 慢的 Plan 被选中（Plan 竞态）

- **Jira**: [CIR-20893] [cloud][26.0.4][AWHKDKHC] 查询卡住，慢的查询plan比快的更优
- **标签**: `ai_new_issue`, `cloud` | 15 comments | **Priority: High**
- **Severity**: High
- **Symptom**: 同一查询时而 200ms、时而卡住数分钟
- **Root cause**: CBO cost estimation 在 cloud 模式下 S3 IO 延迟不确定 + plan cache race
- **关键诊断动作**: EXPLAIN 对比快慢 → `SET enable_plan_cache=false` → Profile 对比

### Case CL4: FDB 偶发堆积

- **Jira**: [CIR-20955] [瑶池][4.1.7] C的fdb偶发堆积
- **标签**: `ai_pending_judgment`, `fdb`, `瑶池` | 15 comments | **Priority: High**
- **Severity**: High
- **Symptom**: meta-service FDB 事务堆积，导致 FE 操作延迟
- **Root cause**: FDB 写入放大或 commit 冲突率升高
- **关键诊断动作**: FDB latency metrics → fe.log meta-service RPC 耗时 → FDB `status json`

### Case CL5: BE 异常重启

- **Jira**: [CIR-20944] [4.0.4] selectdb-cn-83l3tgvd001-be 节点异常重启
- **标签**: `ai_known_issue`, `cloud`, `瑶池` | 3 comments
- **Severity**: Medium
- **Symptom**: cloud 模式下 BE 无 core dump 但进程退出重启
- **Root cause**: 疑似 brpc health check 超时触发 watchdog kill
- **关键诊断动作**: be.out 退出日志 → dmesg OOM killer → `be-metrics --grep brpc`

---

## 诊断模式总结（跨案例共性）

### 方法论
1. **Profile 优先**: 超过半数的性能案例（Q1/Q3/Q4/CL3）第一步都是看 Profile → Plan Time vs ExecTime
2. **区分 base vs cumu compaction**: `type=1` = base, `type=2` = cumu → 不同策略
3. **jemalloc overhead**: RSS 超出 MemTracker 10-20% 是常态 → mem_limit 留足余量
4. **Catalog scan range 耗时**: S3/HDFS/Glue/Iceberg 的慢不在 IO，在 RPC/metadata/partition enumeration
5. **brpc 问题不等于网络问题**: E11/EAGAIN 往往不是网络不通，而是线程池/并发度问题
6. **先止血再根因**: `reset_rpc_channel`、kill query、调小并发参数 → 保留现场证据（pstack/jstack/heap dump）→ 再分析

### 高频根因类别
| 类别 | 代表案例 | 占比 |
|------|----------|------|
| RPC/并发度/线程池 | I4, Q3, CL2 | ~20% |
| 内存泄漏/溢出 | N1, N2, N5, N7, R1, R2 | ~25% |
| Compaction 调度/竞态 | C1, C3, C4, C5 | ~15% |
| Catalog/metadata 交互 | Q1, DL1, DL2, DL3 | ~15% |
| 配置错误/版本兼容 | Q2, D2, N6 | ~10% |
| 代码 bug（空指针/并发） | R3, C2, I5 | ~15% |

---

## 使用方式

在 doris-debug skill 中引用本文档的案例：

```markdown
## Related CIR cases
- [CIR-20928] [E11] Exchange brpc fanout — 高峰期 exchange RPC EAGAIN
- [CIR-20891] Import RPC timed out — heavy work pool 打满
```

每个 skill 的 case 文件应引用至少一个 CIR 真实案例作为背景。排障时优先搜索本索引中相似症状的案例，避免重复排查已知问题。
