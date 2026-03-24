# Deploy to Railway

## Quick Start

### 1. Create Railway project
```bash
# Install Railway CLI
npm i -g @railway/cli
railway login
railway init
```

### 2. Set environment variables
In Railway dashboard → Variables:
```
ANTHROPIC_API_KEY=sk-ant-...
FRED_API_KEY=...
ALPHAVANTAGE_API_KEY=...
BCCH_USER=...
BCCH_PASSWORD=...
JWT_SECRET=<generate with: openssl rand -hex 32>
PORT=8000
```

### 3. Prepare Layout files
Railway needs the Layout platform files. Two options:

**Option A: Copy Layout into deploy/ before pushing**
```bash
# From consejo_ia/
cp -r ../../Layout/greybark_platform.py deploy/layout/
cp ../../Layout/passwords.json deploy/layout/
cp ../../Layout/greybark.db deploy/layout/
cp ../../Layout/seed_test_clients.py deploy/layout/
```

**Option B: Use Railway volume (persistent storage)**
1. Add a volume at `/app/layout` in Railway dashboard
2. Upload files via Railway CLI or init script
3. This keeps the SQLite DB persistent across deploys

### 4. Deploy
```bash
cd consejo_ia/
railway up
```

### 5. Verify
```
https://<your-app>.up.railway.app/login
```

## Architecture in Docker

```
/app/
  consejo_ia/          # Full pipeline code
    deploy/
      app.py           # FastAPI portal
      auth.py          # JWT + bcrypt auth
      static/          # CSS
      web_templates/   # Jinja2 HTML
    run_monthly.py     # Pipeline (subprocess)
    output/            # Shared report output
  layout/              # Platform layer (volume)
    greybark.db        # Client database
    passwords.json     # Bcrypt hashes
    output/            # Per-client report dirs
      greybark/
        2026-03-24/
      demo_corp/
```

## Passwords

Generate/update passwords:
```bash
# From Layout/ directory (local)
python gen_passwords.py greybark NewPassword123!
python gen_passwords.py --show
```

Current credentials:
- `greybark` / `Gr3yb4rk2026!`
- `demo_corp` / `Demo2026!`

## Cost estimate
- Railway Hobby: $5/month (512MB RAM, 1 vCPU)
- Scales to Pro ($20/mo) if needed
- Claude API: ~$2-3 per council session
- Total: ~$7-8/month for 1 monthly run

## Report sync workflow
1. Pipeline runs locally or on Railway: `python run_monthly.py --client greybark --no-confirm`
2. Reports land in `consejo_ia/output/reports/` (shared) + `layout/output/greybark/2026-03-24/` (client)
3. Portal serves from client directory
4. Manual sync: `python sync_reports.py greybark` (copies existing reports to client dir)
