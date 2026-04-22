from models import SessionState

# These process names will be flagged if detected on candidate's machine
BANNED_PROCESSES = [
    "chatgpt", "claude", "copilot", "raycast",
    "popclip", "perplexity", "gemini", "bard",
    "notion ai", "grammarly"
]

def is_banned(process_name: str) -> bool:
    """Check if a running process name matches any banned AI tool."""
    name_lower = process_name.lower()
    return any(banned in name_lower for banned in BANNED_PROCESSES)


def compute_risk_score(state: SessionState) -> int:
    """
    Calculate a 0–100 risk score based on all collected signals.
    Higher = more likely cheating.
    """
    score = 0

    # ── Gaze off-screen percentage ──────────────────────────────────────────
    # Most impactful signal — candidate looking at floating AI window
    if state.gaze_offscreen_pct > 50:
        score += 40
    elif state.gaze_offscreen_pct > 35:
        score += 25
    elif state.gaze_offscreen_pct > 20:
        score += 10

    # ── Banned AI process found ──────────────────────────────────────────────
    # Critical — candidate has AI app running
    if len(state.banned_processes) > 0:
        score += 40

    # ── Paste events ─────────────────────────────────────────────────────────
    if state.paste_count >= 6:
        score += 15
    elif state.paste_count >= 3:
        score += 8

    # ── Tab / window switches ─────────────────────────────────────────────────
    if state.tab_switches >= 5:
        score += 10
    elif state.tab_switches >= 2:
        score += 5

    # ── Inhuman keystroke speed (likely paste disguised as typing) ────────────
    if state.fast_keystroke_count >= 10:
        score += 10
    elif state.fast_keystroke_count >= 5:
        score += 5

    # ── Face anomalies ────────────────────────────────────────────────────────
    if state.no_face_count >= 10:
        score += 10   # candidate left the screen
    if state.multi_face_count >= 3:
        score += 15   # someone else in the room helping

    return min(score, 100)   # cap at 100


def classify_risk(score: int) -> str:
    """Convert numeric score to human-readable level."""
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    return "LOW"