#!/bin/bash
echo "=== Registered Claude Skills ==="
jq '.skills | to_entries | map({name: .key, commands: .value.commands})' ~/.claude/settings.json

echo "=== Checking Graphify Artifacts ==="
graphify update ~/Sterling --no-viz || echo "[WARN] Graphify rebuild failed, but JSON/MD may still exist."

ok_count=0
for f in ~/Sterling/graph.json ~/Sterling/GRAPH_REPORT.md; do
  if [ -f "$f" ]; then
    echo "[OK] Found $f"
    stat -c "Last updated: %y" "$f"
    ok_count=$((ok_count+1))
  else
    echo "[MISSING] $f not found"
  fi
done

if [ $ok_count -eq 2 ]; then
  nodes=$(grep -i "Graph has" ~/Sterling/GRAPH_REPORT.md | grep -o '[0-9]\+' | head -1)
  if [ -n "$nodes" ]; then
    echo ">>> Graphify rebuild succeeded with JSON/MD only (HTML viz skipped). Node count: $nodes"
  else
    echo ">>> Graphify rebuild succeeded with JSON/MD only (HTML viz skipped)."
  fi
else
  echo ">>> Graphify rebuild incomplete — check warnings above."
fi

echo "=== Launching Claude with Statusline ==="
claude <<'INNER'
/statusline
INNER
