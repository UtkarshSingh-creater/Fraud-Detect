"""
ProctorAI — main.py
Wires all routers, middleware, logging, and startup lifecycle.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database      import init_db
from core.logger   import logger, log_ws

from routes.auth       import router as auth_router
from routes.sessions   import router as sessions_router
from routes.websockets import router as ws_router
from routes.export     import router as export_router
from routes.health     import router as health_router


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.bind(module="startup").info("ProctorAI backend starting up...")
    await init_db()
    logger.bind(module="startup").info("Database initialised ✓")
    yield
    logger.bind(module="startup").info("ProctorAI backend shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ProctorAI Backend",
    description="Real-time anti-cheating system for live online interviews",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ──────────────────────────────────────────────────────────────────────

import os
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 1)

    # Skip health checks from logs to avoid noise
    if request.url.path not in ("/health", "/health/live", "/health/ready"):
        logger.bind(module="http").info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms}ms) "
            f"ip={request.client.host if request.client else 'unknown'}"
        )
    return response


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.bind(module="error").error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health_router)        # /health — no auth, checked first
app.include_router(auth_router)          # /auth/login, /auth/me
app.include_router(sessions_router)      # /session/*
app.include_router(ws_router)            # /ws/agent, /ws/dashboard
app.include_router(export_router)        # /export/*


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status":  "ProctorAI backend is running",
        "docs":    "/docs",
        "health":  "/health",
        "version": "1.0.0",
    }