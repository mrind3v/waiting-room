#!/usr/bin/env bash
# Run BEFORE `terraform destroy` so Kubernetes-created AWS resources (NLB, EBS volumes, ENIs)
# are removed first. Otherwise they are orphaned and block VPC deletion / keep billing.
set -euo pipefail
CTX="$(kubectl config current-context)"
echo "kubectl context: $CTX"
case "$CTX" in *kind-*) echo "This is a kind cluster; nothing to clean in AWS." ;; esac
read -r -p "Tear down the Waiting Room workloads in '$CTX'? [yes/N] " ans
[ "$ans" = "yes" ] || { echo "aborted"; exit 1; }

echo "==> stop CI deploys and remove AWS credentials from GitHub"
gh variable set DEPLOY_ENABLED --body false || true
gh secret delete AWS_ACCESS_KEY_ID || true
gh secret delete AWS_SECRET_ACCESS_KEY || true

echo "==> troubleshooting leftovers"
kubectl delete -f troubleshooting/ --ignore-not-found || true

echo "==> application (also deletes the Postgres PVC via the StatefulSet retention policy)"
helm uninstall waiting-room -n waiting-room --wait || true
kubectl -n waiting-room delete pvc --all --wait=true || true

echo "==> monitoring, ingress controller (deletes the NLB), metrics-server"
helm uninstall kps -n monitoring --wait || true
helm uninstall traefik -n traefik --wait || true
helm uninstall metrics-server -n kube-system --wait || true

echo "==> namespaces"
kubectl delete namespace waiting-room monitoring traefik --ignore-not-found --wait=true

echo "==> remaining persistent volumes / load balancer services (should be empty):"
kubectl get pv 2>/dev/null || true
kubectl get svc -A 2>/dev/null | grep LoadBalancer || echo "no LoadBalancer services"
echo "Now run scripts/verify-teardown.sh, then: terraform plan -destroy, review, terraform destroy"
