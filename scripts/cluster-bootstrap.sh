#!/usr/bin/env bash
# Idempotent cluster add-ons: namespaces, secrets, metrics-server, Traefik, kube-prometheus-stack.
# Usage: ./scripts/cluster-bootstrap.sh <kind|eks>
set -euo pipefail
TARGET="${1:?usage: cluster-bootstrap.sh <kind|eks>}"
cd "$(dirname "$0")/.."

TRAEFIK_CHART=41.7.1
METRICS_SERVER_CHART=3.14.0
KPS_CHART=92.7.0

echo "==> context: $(kubectl config current-context)"
kubectl apply -f k8s/namespace.yaml

if [ "$TARGET" = "eks" ]; then
  kubectl apply -f k8s/storageclass-gp3.yaml
  kubectl apply -f k8s/rbac-ci-deployer.yaml
fi

# Secrets are generated in-cluster and never printed or committed.
if ! kubectl -n waiting-room get secret waiting-room-db >/dev/null 2>&1; then
  openssl rand -hex 24 | tr -d '\n' |
    kubectl -n waiting-room create secret generic waiting-room-db --from-file=password=/dev/stdin
fi
if ! kubectl -n monitoring get secret grafana-admin >/dev/null 2>&1; then
  { printf 'admin' > /tmp/.wr-grafana-user; openssl rand -hex 16 | tr -d '\n' > /tmp/.wr-grafana-pass; }
  kubectl -n monitoring create secret generic grafana-admin \
    --from-file=admin-user=/tmp/.wr-grafana-user --from-file=admin-password=/tmp/.wr-grafana-pass
  rm -f /tmp/.wr-grafana-user /tmp/.wr-grafana-pass
fi

helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ >/dev/null
helm repo add traefik https://traefik.github.io/charts >/dev/null
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo update >/dev/null

MS_ARGS=()
[ "$TARGET" = "kind" ] && MS_ARGS=(-f monitoring/metrics-server-values-kind.yaml)
helm upgrade --install metrics-server metrics-server/metrics-server \
  --version "$METRICS_SERVER_CHART" -n kube-system ${MS_ARGS[@]+"${MS_ARGS[@]}"} --wait --timeout 5m

helm upgrade --install traefik traefik/traefik \
  --version "$TRAEFIK_CHART" -n traefik -f "monitoring/traefik-values-$TARGET.yaml" \
  --wait --timeout 10m

helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --version "$KPS_CHART" -n monitoring -f monitoring/kube-prometheus-stack-values.yaml \
  --wait --timeout 10m

echo "==> bootstrap complete"
kubectl get pods -A
