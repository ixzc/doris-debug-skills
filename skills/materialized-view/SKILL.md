---
name: doris-debug-materialized-view
description: >
  Use for Doris sync MV (rollup) miss or async MTMV refresh/rewrite issues.
  Commands: SHOW ALTER TABLE MATERIALIZED VIEW, mv_infos(), EXPLAIN, REFRESH MATERIALIZED VIEW.
version: 0.1.0
category: materialized-view
---

# Materialized View

| Kind | Code area | Check |
|------|-----------|-------|
| Sync | `MaterializedViewHandler` / rollup | `SHOW ALTER TABLE MATERIALIZED VIEW` |
| Async MTMV | `fe/.../mtmv/` | `mv_infos()` RefreshState |

```sql
EXPLAIN SELECT ...;
SELECT * FROM mv_infos('database'='db') WHERE Name='mv';
SET materialized_view_rewrite_enable_contain_external_table=true;
```
