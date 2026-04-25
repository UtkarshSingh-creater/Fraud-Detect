import os
from dotenv import load_dotenv

load_dotenv()

# ── WebSocket ──────────────────────────────────
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:8000/ws/agent")
SESSION_ID    = os.getenv("SESSION_ID",    "session_001")
# FIX: added AGENT_API_KEY — must match backend/.env
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "agent-secret-key-change-this")

# ── Camera ─────────────────────────────────────
CAMERA_INDEX  = 0
FRAME_WIDTH   = 640
FRAME_HEIGHT  = 480
FPS           = 30

# ── Face Detection ─────────────────────────────
FACE_MISSING_ALERT_SECONDS  = 3
FACE_VERIFY_EVERY_N_FRAMES  = 30
FACE_MATCH_TOLERANCE        = 0.55
MAX_ALLOWED_FACES           = 1

# ── Gaze Tracking ──────────────────────────────
GAZE_OFFSCREEN_THRESHOLD_X  = 0.65
GAZE_OFFSCREEN_THRESHOLD_Y  = 0.65
GAZE_LOCK_SECONDS           = 1.5
GAZE_SEND_INTERVAL_MS       = 300

# ── Head Pose ──────────────────────────────────
HEAD_YAW_THRESHOLD          = 25
HEAD_PITCH_THRESHOLD        = 20
HEAD_POSE_ALERT_COUNT       = 3

# ── Liveness ───────────────────────────────────
BLINK_EAR_THRESHOLD         = 0.18
BLINK_CONSEC_FRAMES         = 1
MIN_BLINK_RATE_PER_MINUTE   = 5
MAX_BLINK_RATE_PER_MINUTE   = 50

# ── Behavioral Biometrics ──────────────────────
KEYSTROKE_BASELINE_SECONDS  = 120
KEYSTROKE_ANOMALY_THRESHOLD = 10.0
PASTE_CHAR_THRESHOLD        = 80
MOUSE_SAMPLE_INTERVAL_MS    = 100
MOUSE_SPEED_THRESHOLD       = 3000

# ── Audio ──────────────────────────────────────
AUDIO_SAMPLE_RATE           = 16000
AUDIO_CHUNK_SIZE            = 1024
AUDIO_CHANNELS              = 1
SPEAKER_COUNT_THRESHOLD     = 1
WHISPER_ENERGY_THRESHOLD    = 0.04
NOISE_ANOMALY_THRESHOLD     = 0.85

# ── Object Detection ───────────────────────────
OBJECT_DETECT_INTERVAL_FRAMES = 8
OBJECT_CONFIDENCE_THRESHOLD   = 0.35
BANNED_OBJECT_CLASSES = ["cell phone", "book", "laptop", "remote"]

# ── Deepfake Detection ─────────────────────────
DEEPFAKE_CHECK_INTERVAL_SEC   = 60
DEEPFAKE_CONFIDENCE_THRESHOLD = 0.35   # lowered — more sensitive

# ── Temporal / LSTM ────────────────────────────
TEMPORAL_WINDOW_SIZE          = 60
TEMPORAL_SUSPICIOUS_THRESHOLD = 0.80

# ── Risk Scoring Weights ───────────────────────
RISK_WEIGHTS = {
    "face_missing":        8,
    "multiple_faces":     10,
    "gaze_offscreen":     13,
    "head_pose":          13,
    "liveness_fail":       6,
    "biometric_anomaly":  10,
    "audio_anomaly":       1,
    "deepfake":            4,
    "temporal_pattern":    2,
    "banned_object":      27,
    "tab_switch":          8,
}

RISK_LOW_MAX    = 30
RISK_MEDIUM_MAX = 60

# ── Banned Processes ───────────────────────────
BANNED_PROCESSES = [
    "chatgpt", "claude", "copilot", "raycast",
    "popclip", "perplexity", "gemini", "bard",
    "notion ai", "slack", "whatsapp", "telegram",
]
