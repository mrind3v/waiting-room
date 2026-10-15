.PHONY: up down seed test lint kind-up kind-deploy kind-down tf-plan
SHA ?= $(shell git rev-parse HEAD)

up:        ## full stack in docker compose -> http://localhost:3000
	docker compose up --build -d
down:
	docker compose down
seed:      ## idempotent demo data (4 doctors, 15 patients, 17 appointments)
	docker compose exec backend python -m app.seed
test:      ## needs `docker compose up -d db` and POSTGRES_PASSWORD from .env
	cd backend && set -a && . ../.env && set +a && .venv/bin/pytest -v
lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

kind-up:   ## local cluster + ingress + metrics-server + prometheus/grafana
	kind create cluster --config k8s/kind-config.yaml
	./scripts/cluster-bootstrap.sh kind
kind-deploy: ## deploy chart with images for $(SHA) from GHCR
	helm upgrade --install waiting-room helm/waiting-room -n waiting-room \
	  -f helm/waiting-room/values-kind.yaml \
	  --set backend.image.tag=$(SHA) --set frontend.image.tag=$(SHA) --wait --timeout 10m
kind-down:
	kind delete cluster --name waiting-room

tf-plan:   ## read-only; never apply from the Makefile
	cd terraform && terraform init && terraform plan -out=tfplan
