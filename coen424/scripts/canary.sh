#!/usr/bin/env bash
# Set one canary step: the share of recommendation traffic that goes to v2.
#
#   coen424/scripts/canary.sh 10    # 90% v1 / 10% v2   (first step)
#   coen424/scripts/canary.sh 25    # promote
#   coen424/scripts/canary.sh 0     # ROLLBACK: everything back to v1
#
# It writes the Istio VirtualService, which is the strangler facade: every request
# to "recommendationservice" is sent to subset v1 or v2 according to these weights.
set -euo pipefail

V2="${1:-}"
case "$V2" in
  '' | *[!0-9]*) echo "usage: $0 <percent of traffic to v2, 0-100>" >&2; exit 1 ;;
esac
if [ "$V2" -gt 100 ]; then
  echo "percent must be between 0 and 100" >&2
  exit 1
fi
V1=$((100 - V2))

kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: recommendationservice
  annotations:
    coen424/canary-step: "v1=${V1} v2=${V2}"
spec:
  hosts:
  - recommendationservice
  http:
  - route:
    - destination:
        host: recommendationservice
        subset: v1
      weight: ${V1}
    - destination:
        host: recommendationservice
        subset: v2
      weight: ${V2}
EOF

echo "Canary step set: v1=${V1}%  v2=${V2}%"
