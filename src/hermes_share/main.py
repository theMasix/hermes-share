"""FastAPI application main entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hermes_share.api.routes_mgmt import router as mgmt_router
from hermes_share.api.routes_share import router as share_router
from hermes_share.config import settings
from hermes_share.db.share_store import ShareStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure share database schema is initialized on startup
    ShareStore(db_path=settings.share_db_path)
    yield


app = FastAPI(
    title="Hermes Share",
    description="Live chat sharing companion service for Hermes Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_and_robots_headers(request: Request, call_next):
    response = await call_next(request)
    # Enforce search engine indexing prevention on all share responses
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@app.get("/healthz", tags=["health"])
def health_check():
    """Liveness & readiness health probe for Kubernetes."""
    return {"status": "healthy", "service": "hermes-share"}


# Register routes
app.include_router(mgmt_router)
app.include_router(share_router)

# Mount static files if directory exists
static_path = (
    settings.static_dir
    if settings.static_dir and settings.static_dir.exists()
    else Path("./web/dist").resolve()
)
if (static_path / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=static_path / "assets"),
        name="assets",
    )
