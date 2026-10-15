#!/usr/bin/env bash
# Show how recommendation requests were split between v1 and v2, and v2's quality,
# by counting the request log lines each version wrote in the last N seconds.
#
#   coen424/scripts/traffic-split.sh        # last 120 seconds
#   coen424/scripts/traffic-split.sh 300    # last 5 minutes
#
# A quick local check. The real canary metrics will come from Istio's telemetry.
set -euo pipefail

WINDOW="${1:-120}"

logs() {  # all log lines of every pod with the given version label
  kubectl logs -l "app=recommendationservice,version=$1" -c server \
    --since="${WINDOW}s" --tail=-1 2>/dev/null || true
}
count() { grep -c "$1" || true; }

v1=$(logs v1 | count "Recv ListRecommendations")
v2_lines=$(logs v2 | grep '"event": "list_recommendations"' || true)
v2=$(printf '%s' "$v2_lines" | count '"event"')
v2_valid=$(printf '%s' "$v2_lines" | count '"valid": true')
v2_fallback=$(printf '%s' "$v2_lines" | count '"source": "fallback"')
v2_error=$(printf '%s' "$v2_lines" | count '"status": "error"')

total=$((v1 + v2))
echo "Recommendation requests in the last ${WINDOW}s: ${total}"
if [ "$total" -eq 0 ]; then
  echo "No traffic yet. Is the loadgenerator running?"
  exit 0
fi
echo "  v1: ${v1}  ($((100 * v1 / total))%)"
echo "  v2: ${v2}  ($((100 * v2 / total))%)"

if [ "$v2" -gt 0 ]; then
  p95_index=$(((95 * v2 + 99) / 100))
  p95=$(printf '%s\n' "$v2_lines" \
    | sed -n 's/.*"latency_ms": \([0-9.]*\).*/\1/p' \
    | sort -n | sed -n "${p95_index}p")
  echo "v2 quality:"
  echo "  valid (agent answer used): ${v2_valid}/${v2}  ($((100 * v2_valid / v2))%)"
  echo "  fallbacks: ${v2_fallback}   errors: ${v2_error}"
  echo "  p95 latency: ${p95} ms"
fi
