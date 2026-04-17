#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "🔍 Running preflight checks..."

require_cmd() {
  local cmd="$1"
  local help="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Missing required command: $cmd"
    echo "   $help"
    exit 1
  fi
}

require_cmd docker "Install Docker Desktop (with Compose plugin) and retry."
require_cmd kubectl "Install kubectl and ensure it is available on PATH."
require_cmd minikube "Install minikube and ensure it is available on PATH."

if [[ ! -f "$ROOT_DIR/backend/.env" ]]; then
  echo "❌ Missing backend/.env"
  echo "   Create it from backend/.env.example (or .env.example) and set your values."
  exit 1
fi

if [[ ! -f "$ROOT_DIR/frontend/.env.local" ]]; then
  echo "❌ Missing frontend/.env.local"
  echo "   Create it from frontend/.env.local.example and set your values."
  exit 1
fi

MINIKUBE_STATUS="$(minikube status --format='{{.Host}}' || true)"
if [[ "$MINIKUBE_STATUS" != "Running" ]]; then
  echo "❌ Minikube is not running."
  echo "   Start it first, for example:"
  echo "   minikube start --nodes 3 --cpus 2 --memory 2200 --driver docker --kubernetes-version=v1.28.3"
  exit 1
fi

echo "✅ Minikube is running"

if ! kubectl get namespace monitoring >/dev/null 2>&1; then
  require_cmd helm "Install Helm to auto-install kube-prometheus-stack."
  echo "📦 monitoring namespace not found. Installing Prometheus stack..."
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
  helm repo update >/dev/null
  kubectl create namespace monitoring >/dev/null
  helm install prometheus-stack prometheus-community/kube-prometheus-stack --namespace monitoring --wait
else
  echo "✅ monitoring namespace found"
fi

if ! kubectl get namespace workloads >/dev/null 2>&1; then
  kubectl create namespace workloads >/dev/null
  echo "✅ Created workloads namespace"
else
  echo "✅ workloads namespace found"
fi

if curl -fsS "http://localhost:9090/-/ready" >/dev/null 2>&1; then
  echo "✅ Prometheus endpoint already reachable on localhost:9090"
else
  echo "Starting Prometheus port-forward on localhost:9090"
  nohup kubectl port-forward -n monitoring svc/prometheus-stack-kube-prom-prometheus 9090:9090 > "$ROOT_DIR/prometheus-port-forward.log" 2>&1 &
  sleep 3
fi

echo "Starting docker compose services..."
docker compose up -d --build

echo "🎉 Ready!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
