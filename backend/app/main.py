from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from contextlib import asynccontextmanager
from app.database import engine, Base

# We will import routers here later

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run Alembic migrations
    import subprocess
    try:
        # Run alembic upgrade head
        # We need to run this command. In docker container it should work.
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        print("Database migrations applied.")
    except Exception as e:
        print(f"Error applying migrations: {e}")
        # In production often we don't want to crash, or maybe we do?
        # For now, print error.
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to NetGuard AI API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

from app.routers import auth, devices, monitoring, api_keys
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
app.include_router(devices.router, prefix=f"{settings.API_PREFIX}/inventory", tags=["inventory"])
app.include_router(monitoring.router, prefix=f"{settings.API_PREFIX}/monitoring", tags=["monitoring"])
app.include_router(api_keys.router, prefix=f"{settings.API_PREFIX}/api-keys", tags=["api-keys"])

from app.routers import agents, hotspot, admin
app.include_router(agents.router, prefix=f"{settings.API_PREFIX}/agents", tags=["agents"])
app.include_router(hotspot.router, prefix=f"{settings.API_PREFIX}/hotspot", tags=["hotspot"])
app.include_router(admin.router, prefix=f"{settings.API_PREFIX}/admin", tags=["admin"])

