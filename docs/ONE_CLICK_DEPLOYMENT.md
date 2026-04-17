# One-Click Deployment Guide

Your Compute Allocator now has true **one-click local + cloud deployment** capability. This document explains the new features.

## Part 1: Local One-Click Startup

### Step 1: Set up environment files
```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Then edit both files and fill in your Supabase credentials:
- `SUPABASE_URL` (from Supabase project settings)
- `SUPABASE_SERVICE_ROLE_KEY` (from Supabase project settings)
- `SUPABASE_ANON_KEY` (from Supabase project settings)

**Important:** Never commit `backend/.env` or `frontend/.env.local` to git.

### Step 2: One-command startup
```bash
make up
```

What happens:
1. ✅ Checks all required CLI tools (docker, kubectl, minikube)
2. ✅ Validates environment files exist
3. ✅ Ensures minikube is running
4. ✅ Auto-installs Prometheus stack if not present
5. ✅ Creates monitoring/workloads namespaces
6. ✅ Port-forwards Prometheus on localhost:9090
7. ✅ Starts backend (:8000) + frontend (:3000)

Result: **Full system ready in ~2 minutes.**

### Runtime status flow (important)

Workloads now follow an explicit deploy flow:

1. `pending`
2. `evaluating`
3. `ready_for_deployment`
4. `deploying`
5. `deployed` (or `failed`)

In Docker-only mode (without usable Kubernetes credentials), the backend still completes AI decisioning and moves workload to `ready_for_deployment` so operators can explicitly deploy later.

## Part 2: Simple One-Command Operations

### Available commands
```bash
make help     # List all commands
make up       # Start everything with preflight checks
make down     # Stop all services
make smoke    # Run end-to-end smoke test
make gates    # Run promotion gates locally
make clean    # Stop everything + delete minikube
```

### Examples
```bash
# Typical dev workflow
$ make up      # Start stack
$ make smoke   # Verify smoke test passes
$ make down    # Stop when done

# Test before cloud deployment
$ make gates   # Run promotion gates with health + smoke
```

## Part 3: Promotion Gates (Safety Checks)

**Promotion gates** are automated checks that verify your system is safe to deploy.

### How it works locally
```bash
make gates
```

Output:
```json
{
  "passed": true,
  "checks": [
    {
      "name": "health_check",
      "passed": true,
      "detail": "Health endpoint returned 200"
    },
    {
      "name": "smoke_check",
      "passed": true,
      "detail": "Smoke test passed"
    },
    {
      "name": "policy_compliance",
      "passed": true,
      "detail": "Policy compliance gate disabled"
    },
    {
      "name": "budget_check",
      "passed": true,
      "detail": "Budget gate skipped (no budget/spend values provided)"
    }
  ]
}
```

### Optional: Require smoke test gate
```bash
python backend/promotion/gates.py --api-base-url http://localhost:8000 --require-smoke
```

### Optional: Enforce budget limit
```bash
export BUDGET_LIMIT_USD=100
export CURRENT_MONTHLY_SPEND_USD=45
python backend/promotion/gates.py
```

## Part 4: Cloud One-Click Deploy (GitHub Actions)

### Prerequisites
1. Push your code to GitHub
2. Set up Azure Container Apps (or similar container service)
3. Add GitHub secrets (see below)

### GitHub Secrets Required

Go to: **Settings → Secrets and variables → Actions**

Add these secrets:
```
AZURE_CREDENTIALS              (service principal JSON for Azure)
AZURE_RG                       (resource group name)
STAGING_BACKEND_HEALTH_URL     (e.g., https://allocator-staging.azurewebsites.net/health)
PROD_BACKEND_HEALTH_URL        (e.g., https://allocator.azurewebsites.net/health)
SUPABASE_URL                   (your Supabase URL)
SUPABASE_SERVICE_ROLE_KEY      (your Supabase service role key)
```

### One-Click Deploy
1. Go to your GitHub repo → **Actions**
2. Select **"One-Click Deploy"** workflow
3. Click **"Run workflow"**
4. Choose:
   - `environment`: `staging` or `production`
   - `require_smoke`: `true` (recommended) or `false`
5. Click **"Run workflow"**

What happens automatically:
1. ✅ Checks out your code
2. ✅ Runs local promotion gates (health + optional smoke test)
3. ✅ Builds Docker images for backend + frontend
4. ✅ Pushes to GitHub Container Registry (GHCR)
5. ✅ Deploys to Azure Container Apps
6. ✅ Verifies post-deploy health

Result: **Your code deployed to cloud in ~5 minutes, with safety gates.**

### In-app deployment trigger (Decision Panel)

From the decision page (`/decision/:id`), when workload status is `ready_for_deployment`, the UI shows:

- **Deploy to Local K8s**
- **Deploy to Cloud (Staging)**

When a deployment fails or gets stuck, the same panel now exposes:

- **Retry deployment** (for failed/cancelled runs)
- **Cancel deployment** (for queued/starting/deploying/triggered runs)

These actions call:

`POST /workloads/{workload_id}/deploy`

Additional control endpoints:

- `POST /workloads/{workload_id}/deploy/retry`
- `POST /workloads/{workload_id}/deploy/cancel`

For cloud dispatch from backend, configure in `backend/.env`:

- `GITHUB_REPOSITORY` (`owner/repo`)
- `GITHUB_TOKEN` (token with workflow dispatch permission)
- `GITHUB_DEPLOY_WORKFLOW` (default `deploy.yml`)
- `GITHUB_DEPLOY_REF` (default `main`)

Notes:

- Local deploy trigger is active.
- Cloud deploy trigger now dispatches GitHub Actions via backend when GitHub env vars are configured.

### Deployment progress API

The Decision Panel now polls deployment progress from:

`GET /workloads/{workload_id}/deploy/status`

Returned fields include state, target, mode, message, timestamps, and (for cloud dispatch) workflow URL.

### Monitor deployment
- GitHub Actions logs show all progress
- Deployment blocked if any gate fails
- Post-deploy health check ensures smoke test

## Part 5: Security Best Practices

### Secrets hygiene
- ✅ Templates: `.env.example`, `backend/.env.example`, `frontend/.env.local.example`
- ✅ Actual files: `backend/.env`, `frontend/.env.local` (in `.gitignore`)
- ✅ Cloud: Use GitHub Secrets, never commit to git

### Docker image updates
- Images are pushed to `ghcr.io/${{ github.repository }}/backend:${{ commit-sha }}`
- Each deployment gets a unique SHA-based tag
- Old images remain available for rollback

## Part 6: Troubleshooting

### `make up` fails with "kubectl not found"
Install kubectl:
```bash
# macOS
brew install kubectl

# Windows (PowerShell)
choco install kubernetes-cli

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
```

### `make up` fails with "minikube is not running"
Start minikube:
```bash
minikube start --nodes 3 --cpus 2 --memory 2200 --driver docker --kubernetes-version=v1.28.3
```

### `make smoke` fails with 401 Supabase errors
Check that `backend/.env` and `frontend/.env.local` have correct Supabase credentials.

### GitHub Actions deployment fails
1. Check that Azure secrets are set correctly
2. Verify Azure Container Apps exist
3. Check GitHub Actions logs for detailed errors

## Part 7: Next Steps

### For local development
```bash
# Typical workflow:
make up           # Start everything
npm run dev       # (optional) Frontend hot reload
make smoke        # Test
make down         # Stop
```

### For production deployment
```bash
# Via GitHub Actions (recommended):
# 1. Push your changes
# 2. Go to Actions → "One-Click Deploy" → Run workflow
# 3. Choose production → Run

# Or locally if needed:
make gates --require-smoke
# If gates pass, manually deploy to production container registry
```

### Cost tracking
Enable budget gates:
```bash
export BUDGET_LIMIT_USD=500
export CURRENT_MONTHLY_SPEND_USD=250
make gates
```

---

**You now have enterprise-grade one-click deployment that rivals AWS, Azure, and GitLab! 🚀**
