#!/bin/bash
echo "=== Registered Claude Skills ==="
jq '.skills | to_entries | map({name: .key, commands: .value.commands})' ~/.claude/settings.json

echo "=== Checking Graphify Artifacts ==="
for f in ~/Sterling/graph.json ~/Sterling/GRAPH_REPORT.md; do
  if [ -f "$f" ]; then
    echo "[OK] Found $f"
    stat -c "Last updated: %y" "$f"
  else
    echo "[MISSING] $f not found"
  fi
done

echo "=== Launching Claude with Statusline ==="
claude <<'INNER'
/statusline
INNER
