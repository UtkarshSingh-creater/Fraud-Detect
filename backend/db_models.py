from sqlalchemy import Column, String, Integer, Float, JSON, Text, Boolean
from sqlalchemy import DateTime, func
from database import Base


class DBSession(Base):
    """One row per interview session."""
    __tablename__ = "sessions"

    session_id       = Column(String, primary_key=True, index=True)
    candidate_name   = Column(String, nullable=False)
    risk_score       = Column(Integer, default=0)
    risk_level       = Column(String, default="LOW")
    gaze_offscreen_pct  = Column(Float, default=0.0)
    paste_count      = Column(Integer, default=0)
    tab_switches     = Column(Integer, default=0)
    fast_keystroke_count = Column(Integer, default=0)
    no_face_count    = Column(Integer, default=0)
    multi_face_count = Column(Integer, default=0)
    banned_processes = Column(JSON, default=list)   # stored as JSON array
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DBEvent(Base):
    """One row per event streamed from the agent. Append-only."""
    __tablename__ = "events"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    session_id       = Column(String, index=True, nullable=False)
    event_type       = Column(String, nullable=False)
    payload          = Column(JSON, nullable=False)   # full event dict
    server_timestamp = Column(Float, nullable=False)