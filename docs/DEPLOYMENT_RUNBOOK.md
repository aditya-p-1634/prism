# PRISM Reproducible Deployment Runbook

## Local demonstration

Requirements:

- Docker Desktop with Compose
- 4 GB available memory
- Ports 3000, 5432, and 8000 available

From the repository root:

```powershell
Copy-Item .env.docker.example .env.docker
docker compose --env-file .env.docker -f docker/docker-compose.yml up --build
```

Open:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/api/v1/health/readiness`

The Compose demo deliberately seeds the synthetic Vayu demonstration world.
That seed is for reproducible presentation and testing only; it is not a real
emergency data feed.

## Startup guarantees

The API container:

1. Waits for PostgreSQL health.
2. Applies Alembic migrations.
3. Seeds demo data only when `PRISM_SEED_DEMO=true`.
4. Starts FastAPI only after migration setup completes.

## Production boundary

This Compose file is a reproducible demonstration deployment, not a certified
emergency-operations deployment. Production requires managed secrets, TLS,
identity integration, restricted CORS, backups, PostGIS performance testing,
observability, disaster recovery, and authority-approved operational data.

Never use the demo JWT secret or synthetic seed in production.

## Verification

Windows:

```powershell
.\scripts\verify-release.ps1
```

The script runs focused safety regression tests, Python compilation, frontend
type checking, and the production frontend build.
