from pydantic import BaseModel
from typing import Literal, Optional
import time

# ─── Incoming Events (from candidate's browser/agent) ───────────────────────

class GazeEvent(BaseModel):
    type: Literal["gaze"]
    x: float          # 0.0 to 1.0  (horizontal position)
    y: float          # 0.0 to 1.0  (vertical position)

class PasteEvent(BaseModel):
    type: Literal["paste"]
    char_count: int

class ProcessEvent(BaseModel):
    type: Literal["process"]
    process_name: str

class KeystrokeEvent(BaseModel):
    type: Literal["keystroke"]
    gap_ms: int       # milliseconds between two keystrokes

class TabSwitchEvent(BaseModel):
    type: Literal["tab_switch"]

class FaceEvent(BaseModel):
    type: Literal["face"]
    face_count: int   # 0 = no face, 2+ = multiple people

# ─── Session State (stored in memory per candidate) ──────────────────────────

class SessionState(BaseModel):
    session_id: str
    candidate_name: str
    risk_score: int = 0
    risk_level: str = "LOW"
    gaze_offscreen_pct: float = 0.0
    paste_count: int = 0
    tab_switches: int = 0
    fast_keystroke_count: int = 0
    no_face_count: int = 0
    multi_face_count: int = 0
    banned_processes: list[str] = []
    events: list[dict] = []
    created_at: float = time.time()

# ─── HTTP Request Bodies ──────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    session_id: str
    candidate_name: str