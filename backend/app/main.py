from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run Alembic migrations
    import subprocess
    
    try:
        logger.info("Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Database migrations applied successfully.")
        if result.stdout:
            logger.debug(f"Migration output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed with exit code {e.returncode}")
        logger.error(f"Migration error: {e.stderr}")
        # In production, we might want to crash or continue
        # For now, log error but continue (existing data should still work)
    except Exception as e:
        logger.error(f"Unexpected error during migrations: {e}", exc_info=True)
    
    # Verify TimescaleDB hypertable exists
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'metrics'")
            )
            hypertable = result.first()
            if hypertable:
                logger.info("TimescaleDB hypertable 'metrics' verified.")
            else:
                logger.warning("TimescaleDB hypertable 'metrics' not found. Attempting to create...")
                try:
                    await conn.execute(
                        text("SELECT create_hypertable('metrics', 'time', if_not_exists => TRUE)")
                    )
                    logger.info("TimescaleDB hypertable 'metrics' created.")
                except Exception as ht_error:
                    logger.warning(f"Could not create hypertable (may already exist or table not ready): {ht_error}")
    except Exception as e:
        logger.warning(f"Could not verify TimescaleDB hypertable: {e}")
        # Non-critical, continue startup
    
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

from app.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Security Headers Middleware
from app.core.middleware import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to NetGuard AI API"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint with database connectivity check."""
    try:
        # Check database connectivity
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.warning(f"Health check database connection failed: {e}")
        return {"status": "degraded", "database": "disconnected"}

@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe - checks database connectivity."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "database": "disconnected"}
        )

@app.get("/live")
async def liveness_check():
    """Kubernetes liveness probe - basic alive check."""
    return {"status": "alive"}

from app.routers import auth, devices, monitoring, api_keys
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
app.include_router(devices.router, prefix=f"{settings.API_PREFIX}/inventory", tags=["inventory"])
app.include_router(monitoring.router, prefix=f"{settings.API_PREFIX}/monitoring", tags=["monitoring"])
app.include_router(api_keys.router, prefix=f"{settings.API_PREFIX}/api-keys", tags=["api-keys"])

from app.routers import agents, hotspot, admin
app.include_router(agents.router, prefix=f"{settings.API_PREFIX}/agents", tags=["agents"])
app.include_router(hotspot.router, prefix=f"{settings.API_PREFIX}/hotspot", tags=["hotspot"])
app.include_router(admin.router, prefix=f"{settings.API_PREFIX}/admin", tags=["admin"])

# Global Exception Handlers
from app.core.exceptions import (
    validation_exception_handler,
    not_found_handler,
    internal_server_error_handler,
    general_exception_handler
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(500, internal_server_error_handler)
app.add_exception_handler(Exception, general_exception_handler)
