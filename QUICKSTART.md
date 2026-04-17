# 🚀 Quick Start: One-Click Deployment

## 30-Second Local Setup

```bash
# 1. Create environment files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# 2. Edit with your Supabase credentials
# - SUPABASE_URL
# - SUPABASE_SERVICE_ROLE_KEY
# - SUPABASE_ANON_KEY

# 3. Start everything
make up                    # Linux/macOS
deploy.bat up              # Windows
```

**Result: Full stack running in ~2 minutes.**

---

## One-Click Commands

### Local (no waiting for cloud)
```bash
make up       # Start with preflight checks
make smoke    # Run tests
make gates    # Run safety checks
make down     # Stop
make clean    # Stop + delete minikube
```

### Windows
```bash
deploy.bat up
deploy.bat smoke
deploy.bat gates
deploy.bat down
deploy.bat clean
```

---

## One-Click Cloud Deploy

1. **GitHub → Actions → "One-Click Deploy"**
2. **Run workflow** (choose staging or production)
3. **Wait 5 minutes** for full deployment

### Setup (one-time, ~5 minutes)
1. Push code to GitHub
2. Go to **Settings → Secrets → Actions**
3. Add Azure + Supabase secrets (see [ONE_CLICK_DEPLOYMENT.md](docs/ONE_CLICK_DEPLOYMENT.md))
4. Done

---

## What Happens Automatically

### Local startup (`make up`)
✅ Check docker, kubectl, minikube installed  
✅ Verify .env files exist  
✅ Ensure minikube is running  
✅ Install Prometheus if missing  
✅ Create namespaces  
✅ Port-forward Prometheus  
✅ Start backend + frontend  

### Cloud deploy (GitHub Actions)
✅ Run health checks  
✅ Run smoke tests (if enabled)  
✅ Build Docker images  
✅ Push to GitHub Container Registry  
✅ Deploy to Azure Container Apps  
✅ Verify post-deploy health  

**If any check fails → deployment blocked. Safe by default.**

---

## Secrets Checklist

### Local
```bash
backend/.env                  ← Created (from template)
frontend/.env.local           ← Created (from template)
# Fill in your Supabase credentials
```

### GitHub (cloud)
Go to **Settings → Secrets → Actions** → Add:
```
AZURE_CREDENTIALS              ← Service principal JSON
AZURE_RG                       ← Resource group name
STAGING_BACKEND_HEALTH_URL     ← Post-deploy health endpoint
PROD_BACKEND_HEALTH_URL        ← Post-deploy health endpoint
SUPABASE_URL                   ← (optional for smoke tests)
SUPABASE_SERVICE_ROLE_KEY      ← (optional for smoke tests)
```

---

## Files You Need to Know

| File | Purpose |
|------|---------|
| [start.sh](../start.sh) | Local preflight checks + startup |
| [Makefile](../Makefile) | Simple commands (Linux/macOS) |
| [deploy.bat](../deploy.bat) | Simple commands (Windows) |
| [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) | Cloud one-click deploy |
| [backend/promotion/gates.py](../backend/promotion/gates.py) | Safety checks before deploy |
| [docs/ONE_CLICK_DEPLOYMENT.md](ONE_CLICK_DEPLOYMENT.md) | Full guide (read this!) |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `make: command not found` | Windows? Use `deploy.bat` instead |
| `kubectl not found` | Install kubectl (brew, choco, apt) |
| `minikube not running` | Run `minikube start --nodes 3 --cpus 2 --memory 2200 --driver docker` |
| `401 Supabase errors` | Check `.env` files have correct credentials |
| `GitHub deploy fails` | Check GitHub Secrets are set correctly |

---

## You Now Have

✅ **Local one-click**: `make up` (or `deploy.bat up`)  
✅ **Cloud one-click**: GitHub Actions workflow  
✅ **Safety gates**: Health + smoke checks  
✅ **Secrets vault**: No leaks via `.gitignore`  
✅ **Production-ready**: Docker images + Kubernetes ready  

**This is enterprise-grade deployment. You're done. Ship it.** 🚀

---

For details, see [docs/ONE_CLICK_DEPLOYMENT.md](ONE_CLICK_DEPLOYMENT.md)
