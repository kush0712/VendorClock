"""
VendorClock FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import engine, Base

# Import all models so Alembic can detect them
from app.models import User, Vendor, Invoice, RawIngestion  # noqa: F401

# API routes
from app.api.routes.auth import router as auth_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.vendors import router as vendors_router
from app.api.routes.invoices import invoice_router, dashboard_router
from app.api.routes.exports import router as exports_router
from app.api.routes.settings import router as settings_router


# Global rate limiter (used by auth router's @limiter.limit decorators)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (in dev; use Alembic migrations in prod)
    if settings.APP_ENV == "development":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="VendorClock API",
    description=(
        "Buyer-side compliance and cash-priority tool for "
        "Section 43B(h) / Section 37(2)(g), Income Tax Act 2025. "
        "Tracks MSE invoice payment deadlines and generates audit exports."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── Rate limiter state + error handler ────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(vendors_router)
app.include_router(invoice_router)
app.include_router(dashboard_router)
app.include_router(exports_router)
app.include_router(settings_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "VendorClock API",
        "citation": settings.SECTION_CITATION_COMBINED,
        "env": settings.APP_ENV,
    }
