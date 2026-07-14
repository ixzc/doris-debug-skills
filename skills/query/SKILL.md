---
name: doris-debug-query
description: >
  Use for Apache Doris slow/hanging/timeout queries. Covers FE planner (Nereids timeout),
  BE Profile bottlenecks, and Exchange WaitForData / brpc E1008 on port 8060.
  Session vars: enable_profile, query_timeout, nereids_timeout_second.
version: 0.1.0
category: query
---

# Query Troubleshooting

## Causes

| ID | Cause | Evidence |
|----|-------|----------|
| A | Client timeout too small | `query_timeout` vs Profile wall |
| B | Planner | `Nereids cost too much time` / `nereids_timeout_second` |
| C | BE compute (scan/join/spill) | Profile active ExecTime |
| D | Exchange / brpc | WaitForData ≈ timeout; `failed to send brpc when exchange`; `[E1008]` on `:8060` |

## 10 min

```sql
SET enable_profile = true;
-- reproduce
```

```bash
./scripts/doris-debug log-grep fe/log be/log --query-id "$QID" --pack planner
./scripts/doris-debug log-grep be/log --query-id "$QID" --pack exchange
./scripts/doris-debug audit-topk fe/log/fe.audit.log -k 20 --min-ms 5000
```

Planner mitigation (session only): `SET disable_join_reorder=true;` for fat ETL joins; fix stats with `ANALYZE`.

Profile interpretation: prefer active time over Wait\*; companion skill `doris-profile-reader` if available.

## Cause D — Exchange / brpc

Code facts (apache/doris):

1. Error text in `be/src/exec/operator/exchange_sink_buffer.h`.
2. `GET /api/reset_rpc_channel/{endpoints}` clears **`brpc_internal_client_cache` only** (`reset_rpc_channel_action.cpp`).
3. `enable_brpc_connection_check` (default false) → `FragmentMgr::_check_brpc_available` hand_shake; consecutive failures erase internal cache.

```bash
curl -s "http://$BE:8040/api/reset_rpc_channel/all"
```

```properties
# be.conf — restart for static DEFINE_Bool
enable_brpc_connection_check = true
brpc_connection_check_timeout_ms = 10000
```

Do not trust ICMP alone. Check `priority_networks`.

## Source

- `SessionVariable.java` — `QUERY_TIMEOUT`, `NEREIDS_TIMEOUT_SECOND`
- Profile WaitForData — exchange source operator
- `exchange_sink_buffer.h`, `reset_rpc_channel_action.cpp`, `fragment_mgr.cpp`
