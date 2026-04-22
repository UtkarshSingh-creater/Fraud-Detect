from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from core.config import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    INTERVIEWER_USERNAME, INTERVIEWER_PASSWORD, AGENT_API_KEY
)

# ── Password hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pre-hash the password from .env at startup
HASHED_PASSWORD = pwd_context.hash(INTERVIEWER_PASSWORD)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    username: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── OAuth2 scheme (reads Bearer token from Authorization header) ──────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_interviewer(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency — inject into any route that requires interviewer login.
    Raises 401 if token is missing, expired, or tampered.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exc
        return username
    except JWTError:
        raise credentials_exc


# ── API Key for Agent (Electron app) ─────────────────────────────────────────

api_key_header = APIKeyHeader(name="X-Agent-API-Key", auto_error=False)


def verify_agent_key(api_key: str = Depends(api_key_header)):
    """
    Dependency — inject into routes/websockets that only the Electron agent should call.
    """
    if api_key != AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing agent API key"
        )
    return api_key


# ── WebSocket token verifier (tokens can't use headers easily) ───────────────

def verify_ws_token(token: str) -> str:
    """
    Verify a JWT passed as a query param for WebSocket connections.
    Returns username on success, raises WebSocket close on failure.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise ValueError("No subject in token")
        return username
    except (JWTError, ValueError):
        raise HTTPException(status_code=403, detail="Invalid WebSocket token")


def verify_ws_agent_key(api_key: str):
    """Verify the agent API key passed as a query param for WebSocket."""
    if api_key != AGENT_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid agent key for WebSocket")