# ─────────────────────────────────────────────────────
# config.py — Central configuration for ProctorAI
# All thresholds, limits and settings live here
# ─────────────────────────────────────────────────────

import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# ── WebSocket ──────────────────────────────────
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:8000/ws/agent")
SESSION_ID    = os.getenv("SESSION_ID", "session_001")

# ── Camera ─────────────────────────────────────
CAMERA_INDEX  = 0          # 0 = default webcam
FRAME_WIDTH   = 640
FRAME_HEIGHT  = 480
FPS           = 30

# ── Face Detection ─────────────────────────────
FACE_MISSING_ALERT_SECONDS  = 3     # alert if no face for 3 seconds
FACE_VERIFY_EVERY_N_FRAMES  = 30    # re-verify identity every 30 frames
FACE_MATCH_TOLERANCE        = 0.55  # lower = stricter match (0.0 to 1.0)
MAX_ALLOWED_FACES           = 1     # flag if more than 1 face detected

# ── Gaze Tracking ──────────────────────────────
GAZE_OFFSCREEN_THRESHOLD_X  = 0.65  # x > 0.65 = looking right off screen
GAZE_OFFSCREEN_THRESHOLD_Y  = 0.65  # y > 0.65 = looking down off screen
GAZE_LOCK_SECONDS           = 1.5   # flag if gaze locked to one spot for 1.5s
GAZE_SEND_INTERVAL_MS       = 300   # send gaze event every 300ms

# ── Head Pose ──────────────────────────────────
HEAD_YAW_THRESHOLD          = 25    # degrees left/right before flagging
HEAD_PITCH_THRESHOLD        = 20    # degrees up/down before flagging
HEAD_POSE_ALERT_COUNT       = 3    # flag after 1 consecutive violation

# ── Liveness ───────────────────────────────────
BLINK_EAR_THRESHOLD         = 0.18  # Eye Aspect Ratio below this = blink (raised for webcam)
BLINK_CONSEC_FRAMES         = 1     # frames eye must be closed to count (1 = more sensitive)
MIN_BLINK_RATE_PER_MINUTE   = 5     # below this = possibly not live
MAX_BLINK_RATE_PER_MINUTE   = 50    # above this = nervous/suspicious

# ── Behavioral Biometrics ──────────────────────
KEYSTROKE_BASELINE_SECONDS  = 120   # build baseline for first 2 minutes
KEYSTROKE_ANOMALY_THRESHOLD = 10.0   # flag if deviation > 2.5x baseline avg
PASTE_CHAR_THRESHOLD        = 80   # flag paste if more than 100 chars
MOUSE_SAMPLE_INTERVAL_MS    = 100   # sample mouse position every 100ms
MOUSE_SPEED_THRESHOLD       = 3000  # pixels/sec — above this is suspicious

# ── Audio ──────────────────────────────────────
AUDIO_SAMPLE_RATE           = 16000
AUDIO_CHUNK_SIZE            = 1024
AUDIO_CHANNELS              = 1
SPEAKER_COUNT_THRESHOLD     = 1     # flag if more than 1 speaker detected
WHISPER_ENERGY_THRESHOLD    = 0.04  # low energy + voice = whisper
NOISE_ANOMALY_THRESHOLD     = 0.85  # sudden spike in audio energy

# ── Object Detection (YOLOv8-nano) ─────────────────
OBJECT_DETECT_INTERVAL_FRAMES = 8   # run YOLO every 15 frames (~2/sec @ 30fps)
OBJECT_CONFIDENCE_THRESHOLD   = 0.35 # minimum YOLO confidence to report
# Object labels (COCO) that are banned during an exam session
BANNED_OBJECT_CLASSES = ["cell phone", "book", "laptop", "remote"]

# ── Deepfake Detection ─────────────────────────
DEEPFAKE_CHECK_INTERVAL_SEC = 60    # run deepfake check every 60 seconds
DEEPFAKE_CONFIDENCE_THRESHOLD = 0.65 # flag if synthetic confidence > 0.75

# ── Temporal / LSTM ────────────────────────────
TEMPORAL_WINDOW_SIZE        = 60    # analyze last 60 events as a sequence
TEMPORAL_SUSPICIOUS_THRESHOLD = 0.80 # flag if LSTM confidence > 0.80

# ── Risk Scoring Weights ───────────────────────
# All weights must add up to 100
# Sustained-detection multiplier (risk_engine.py) scales each
# contribution up to 2× after 2 seconds of continuous flagging.
RISK_WEIGHTS = {
    "face_missing":        8,   # ---
    "multiple_faces":     10,   # ---
    "gaze_offscreen":     13,   # primary behavioural signal
    "head_pose":          13,   # primary behavioural signal
    "liveness_fail":       6,   # blink / movement check
    "biometric_anomaly":   10,   # keystroke / mouse oddity
    "audio_anomaly":       1,   # voice / noise
    "deepfake":            4,   # synthetic face
    "temporal_pattern":    2,   # LSTM pattern
    "banned_object":      27,   # HIGHEST — phone/book = direct cheating tool
    "tab_switch":          8,   # window / app switch
}
# Weights sum: 8+10+13+13+6+4+3+4+4+30+5 = 100

# Risk level thresholds (with sustained-escalation multiplier):
#   First phone detection alone  → score ≈ 30  → MEDIUM
#   Phone held 2 s alone         → score ≈ 60  → HIGH
#   All signals together 2 s     → score ≈ 90+ → HIGH (capped 100)
RISK_LOW_MAX    = 30   # 0–25   = LOW
RISK_MEDIUM_MAX = 60    # 26–55  = MEDIUM
                        # 56–100 = HIGH

# ── Banned Processes ───────────────────────────
BANNED_PROCESSES = [
    "chatgpt",
    "claude",
    "copilot",
    "raycast",
    "popclip",
    "perplexity",
    "gemini",
    "bard",
    "notion ai",
    "slack",          # remove if interviewer uses slack
    "whatsapp",
    "telegram",
]

