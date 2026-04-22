from fastapi import APIRouter, HTTPException
from models import SessionState, CreateSessionRequest
router = APIRouter(prefix="/session", tags=["Sessions"])

# Shared in-memory store — imported and used by websockets.py too
sessions: dict[str, SessionState] = {}


@router.post("/create")
def create_session(body: CreateSessionRequest):
    """Create a new interview session before the candidate joins."""
    if body.session_id in sessions:
        raise HTTPException(status_code=400, detail="Session ID already exists")

    sessions[body.session_id] = SessionState(
        session_id=body.session_id,
        candidate_name=body.candidate_name
    )
    return {
        "ok": True,
        "session_id": body.session_id,
        "candidate_name": body.candidate_name
    }


@router.get("/{session_id}")
def get_session(session_id: str):
    """Fetch current state and full event log for a session."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.get("/")
def list_sessions():
    """List all active sessions (for the interviewer's overview page)."""
    return [
        {
            "session_id": s.session_id,
            "candidate_name": s.candidate_name,
            "risk_score": s.risk_score,
            "risk_level": s.risk_level,
        }
        for s in sessions.values()
    ]


@router.delete("/{session_id}")
def delete_session(session_id: str):
    """End and remove a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    return {"ok": True, "deleted": session_id}