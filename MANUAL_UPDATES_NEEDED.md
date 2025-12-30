# Manual Updates Needed for main.py

Due to file editing limitations, the following updates need to be manually applied to `backend/app/main.py`:

## 1. Add Missing Imports (at the top of the file)

Add these imports after line 8:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
```

## 2. Add Rate Limiter and Security Headers (after line 75, before CORS middleware)

```python
# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            # Only add HSTS in production
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

## 3. Update Health Check Endpoint (replace lines 89-91)

Replace:
```python
@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

With:
```python
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
```

## 4. Create .env.example file

Create `.env.example` in the root directory with the template from the plan (Phase 1.1).

## Notes

- All other changes have been implemented automatically
- These manual updates are needed due to file editing limitations
- After applying these changes, test the application thoroughly
