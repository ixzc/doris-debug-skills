#!/usr/bin/env bash
set -euo pipefail
TOOL=""; TARGET=""; VERBOSE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool) TOOL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) echo "Usage: $0 --tool claude-code|cursor --target PATH"; exit 0 ;;
    *) echo "Unknown $1"; exit 1 ;;
  esac
done
[[ -n "$TOOL" && -n "$TARGET" ]] || { echo "need --tool and --target"; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
SKILLS=(query import compaction node materialized-view tablet deployment data-lake resource-isolation cloud)

install_claude() {
  local dest="$1"
  mkdir -p "$dest/doris-debug-shared/"{references,guides}
  cp -R "$ROOT/references/." "$dest/doris-debug-shared/references/"
  cp -R "$ROOT/guides/." "$dest/doris-debug-shared/guides/"
  mkdir -p "$dest/doris-debug"
  cat > "$dest/doris-debug/SKILL.md" <<'EOF'
---
name: doris-debug
description: >
  Apache Doris production diagnostics router. Use for slow queries, import/WAL,
  compaction -235, Exchange/brpc issues, MV, tablet, lakehouse, cloud. Routes to
  doris-debug-* skills and shared source-mapped references.
---
# Doris Debug Router
1. Read `../doris-debug-shared/references/01-common-commands.md` and `02-source-map.md`.
2. Pick skill: query | import | compaction | node | materialized-view | tablet | deployment | data-lake | resource-isolation | cloud.
3. Prefer CLI: `PYTHONPATH=<repo>/python python3 -m doris_debug ...`
EOF
  for s in "${SKILLS[@]}"; do
    mkdir -p "$dest/doris-debug-$s/references"
    cp "$ROOT/skills/$s/SKILL.md" "$dest/doris-debug-$s/SKILL.md"
    if [[ -d "$ROOT/skills/$s/references" ]]; then
      cp -R "$ROOT/skills/$s/references/." "$dest/doris-debug-$s/references/" || true
    fi
    [[ -n "$VERBOSE" ]] && echo "installed doris-debug-$s"
  done
  mkdir -p "$dest/doris-debug-shared/python"
  cp -R "$ROOT/python/doris_debug" "$dest/doris-debug-shared/python/"
  # drop removed skill if previously installed
  rm -rf "$dest/doris-debug-brpc-exchange"
  echo "OK -> $dest"
}

install_cursor() {
  local dest="$1"; mkdir -p "$dest"
  rm -f "$dest/doris-debug-brpc-exchange.mdc"
  for s in "${SKILLS[@]}"; do
    {
      echo "---"
      echo "description: Doris debug - $s"
      echo "alwaysApply: false"
      echo "---"
      echo
      cat "$ROOT/skills/$s/SKILL.md"
    } > "$dest/doris-debug-$s.mdc"
  done
  echo "OK -> $dest"
}

case "$TOOL" in
  claude-code) install_claude "$TARGET" ;;
  cursor) install_cursor "$TARGET" ;;
  *) echo "bad tool"; exit 1 ;;
esac
