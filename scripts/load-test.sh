#!/usr/bin/env bash
# Generates real CPU load on the backend (DB-backed endpoint) so the HPA scales.
# Usage: ./scripts/load-test.sh [duration-seconds]   (default 240)
set -euo pipefail
NS=waiting-room
DURATION="${1:-240}"
SVC=$(kubectl -n "$NS" get svc -l app.kubernetes.io/component=backend -o jsonpath='{.items[0].metadata.name}')
DAY=$(date +%F)

kubectl -n "$NS" delete job wr-load-test --ignore-not-found >/dev/null
kubectl -n "$NS" apply -f - <<YAML
apiVersion: batch/v1
kind: Job
metadata: {name: wr-load-test}
spec:
  ttlSecondsAfterFinished: 120
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      securityContext: {runAsNonRoot: true, runAsUser: 65534, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: fortio
          image: fortio/fortio:1.76.0
          args: ["load", "-c", "32", "-qps", "0", "-t", "${DURATION}s", "-quiet",
                 "http://${SVC}:8000/api/appointments?date=${DAY}"]
          securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}}
YAML
echo "Load running for ${DURATION}s. Watching the HPA (Ctrl-C to stop watching)..."
kubectl -n "$NS" get hpa -w
