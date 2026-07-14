---
name: doris-debug-node
description: >
  Use for Doris FE/BE OOM, crash, or false Alive. BE: MemTrackerLimiter lines in be.WARNING;
  FE: JVM heap / jstack. Distinguish heartbeat Alive from query/brpc serving health.
version: 0.1.0
category: node
---

# Node Health

```bash
./scripts/doris-debug log-grep be/log --pack memory
dmesg -T | grep -i "killed process" | tail
jstack ../fe.pid > /tmp/fe.jstack
```

If Alive=true but queries fail with exchange / brpc errors → **query** (Cause D).
