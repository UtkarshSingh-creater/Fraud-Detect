"""
Structured Logger
─────────────────
Uses loguru for structured, leveled, rotating log output.

Features:
- All logs go to stdout (Docker-friendly — captured by container runtime)
- Logs also written to /logs/proctor.log with daily rotation + 7-day retention
- Every log line is JSON-formatted in production for ingestion by Datadog / Loki / CloudWatch
- Convenience helpers: log_event(), log_ws(), log_auth(), log_db()

Usage:
    from core.logger import logger, log_event, log_ws, log_auth

    logger.info("Server started")
    log_ws("agent_connect", session_id="abc123", ip="1.2.3.4")
    log_event("gaze", session_id="abc123", risk_score=45)
    log_auth("login_success", username="admin")
"""

import sys
import os
from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────

ENV          = os.getenv("ENV", "development")          # "production" enables JSON logs
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR      = os.getenv("LOG_DIR", "logs")
LOG_FILE     = os.path.join(LOG_DIR, "proctor.log")

os.makedirs(LOG_DIR, exist_ok=True)

# ── Format ────────────────────────────────────────────────────────────────────

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[module]: <18}</cyan> | "
    "{message}"
)

JSON_FORMAT = (
    '{{"time":"{time:YYYY-MM-DDTHH:mm:ss.SSS}Z",'
    '"level":"{level}",'
    '"module":"{extra[module]}",'
    '"message":"{message}",'
    '"extra":{extra}}}'
)

# ── Sink setup ────────────────────────────────────────────────────────────────

# Remove default handler
logger.remove()

# Console — human-readable in dev, JSON in production
if ENV == "production":
    logger.add(
        sys.stdout,
        format=JSON_FORMAT,
        level=LOG_LEVEL,
        colorize=False,
        serialize=True,     # loguru native JSON serialization
    )
else:
    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=LOG_LEVEL,
        colorize=True,
    )

# File — always JSON, rotating, 7-day retention
logger.add(
    LOG_FILE,
    format=JSON_FORMAT,
    level="DEBUG",
    rotation="00:00",       # rotate at midnight
    retention="7 days",
    compression="gz",
    serialize=True,
    enqueue=True,           # async write — doesn't block the event loop
)

# Bind a default "module" context so every log line has the field
logger = logger.bind(module="core")


# ── Convenience helpers ───────────────────────────────────────────────────────

def log_ws(action: str, **kwargs):
    """Log a WebSocket lifecycle event."""
    logger.bind(module="websocket").info(
        f"{action} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )

def log_event(event_type: str, **kwargs):
    """Log an incoming agent event (gaze, paste, process, etc.)."""
    logger.bind(module="event").debug(
        f"event={event_type} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )

def log_auth(action: str, **kwargs):
    """Log an auth action (login, token validation, rejection)."""
    logger.bind(module="auth").info(
        f"{action} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )

def log_db(action: str, **kwargs):
    """Log a database operation."""
    logger.bind(module="database").debug(
        f"{action} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )

def log_rate_limit(reason: str, **kwargs):
    """Log a rate limit hit — always WARNING level."""
    logger.bind(module="rate_limiter").warning(
        f"RATE_LIMITED: {reason} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )

def log_security(reason: str, **kwargs):
    """Log a security event — always WARNING or ERROR level."""
    logger.bind(module="security").warning(
        f"SECURITY: {reason} | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())
    )