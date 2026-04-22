from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from datetime import timedelta

from core.auth import (
    verify_password, create_access_token,
    HASHED_PASSWORD, get_current_interviewer
)
from core.config import INTERVIEWER_USERNAME, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Interviewer login. Returns a JWT Bearer token.
    Use: POST /auth/login with form fields: username + password
    """
    if form_data.username != INTERVIEWER_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, HASHED_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": form_data.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_me(username: str = Depends(get_current_interviewer)):
    """Check who you're logged in as. Protected route."""
    return {"username": username, "role": "interviewer"}