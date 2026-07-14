---
name: doris-debug-compaction
description: >
  Use for Doris -235 / too many versions and compaction lag. Error raised in
  RowsetBuilder::check_tablet_version_count when version_count > max_tablet_version_num
  (default 2000) or meta serialize size limit.
version: 0.1.0
category: compaction
---

# Compaction / Versions

## Code

`be/src/storage/rowset_builder.cpp`:

- `version_count > max_version_config` → `Status::Error<TOO_MANY_VERSION>(...)`
- Suggests reduce load frequency or raise `max_tablet_version_num` /
  `time_series_max_tablet_version_num` in `be.conf`
- Near limit triggers cumulative compaction submit

Defaults (`config.cpp`): `max_tablet_version_num=2000`, `time_series_max_tablet_version_num=20000`.

## Actions

1. Confirm with `./scripts/doris-debug log-grep be/log --pack versions`
2. Slow ingest / enlarge group commit batches
3. Compaction thread / disk IO capacity
4. Raising max_tablet_version_num is a temporary valve — fix ingest vs compaction balance

```bash
./scripts/doris-debug be-metrics --be http://$BE:8040 --grep compaction
```
