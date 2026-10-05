from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.hazards import router as hazards_router
from app.api.v1.people import router as people_router
from app.api.v1.destinations import router as destinations_router
from app.api.v1.routing import router as routing_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.snapshots import router as snapshots_router
from app.api.v1.audit import router as audit_router
from app.api.v1.reports import router as reports_router
from app.api.v1.health import router as health_router
from app.api.v1.simulation import router as simulation_router
from app.api.v1.hazard_prediction import router as hazard_prediction_router
from app.api.v1.hazard_observation import router as hazard_observation_router

app = FastAPI(
    title="PRISM — Predictive Relocation & Infrastructure Safety Matrix",
    description="Automated Decision-Support Platform for SIH 26191: Red Zones, Dynamic Carrying Capacity, and Relocation Optimization.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware for Correlation ID and performance logging
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    return response

# Mount API Routers under /api/v1
api_v1_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(hazards_router, prefix=api_v1_prefix)
app.include_router(people_router, prefix=api_v1_prefix)
app.include_router(destinations_router, prefix=api_v1_prefix)
app.include_router(routing_router, prefix=api_v1_prefix)
app.include_router(scenarios_router, prefix=api_v1_prefix)
app.include_router(simulation_router, prefix=api_v1_prefix)
app.include_router(dashboard_router, prefix=api_v1_prefix)
app.include_router(snapshots_router, prefix=api_v1_prefix)
app.include_router(audit_router, prefix=api_v1_prefix)
app.include_router(reports_router, prefix=api_v1_prefix)
app.include_router(health_router, prefix=api_v1_prefix)
app.include_router(hazard_prediction_router, prefix=api_v1_prefix)
app.include_router(hazard_observation_router, prefix=api_v1_prefix)

@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "system": "PRISM",
        "env": settings.PRISM_ENV,
        "config_version": settings.CONFIG_VERSION,
        "active_crs": settings.COMPUTATIONAL_CRS
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
