# ─────────────────────────────────────────────
# config.py — Central configuration for ProctorAI
# All thresholds, limits and settings live here
# ─────────────────────────────────────────────

# ── WebSocket ──────────────────────────────────
WEBSOCKET_URL = "ws://localhost:8000/ws/agent"   # backend team will replace this
SESSION_ID    = "session_001"                     # will be passed dynamically later

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
GAZE_OFFSCREEN_THRESHOLD_X  = 0.70  # x > 0.70 = looking right off screen
GAZE_OFFSCREEN_THRESHOLD_Y  = 0.70  # y > 0.70 = looking down off screen
GAZE_LOCK_SECONDS           = 3     # flag if gaze locked to one spot for 3s
GAZE_SEND_INTERVAL_MS       = 500   # send gaze event every 500ms

# ── Head Pose ──────────────────────────────────
HEAD_YAW_THRESHOLD          = 30    # degrees left/right before flagging
HEAD_PITCH_THRESHOLD        = 25    # degrees up/down before flagging
HEAD_POSE_ALERT_COUNT       = 3     # flag after 3 consecutive violations

# ── Liveness ───────────────────────────────────
BLINK_EAR_THRESHOLD         = 0.20  # Eye Aspect Ratio below this = blink
BLINK_CONSEC_FRAMES         = 2     # frames eye must be closed to count
MIN_BLINK_RATE_PER_MINUTE   = 5     # below this = possibly not live
MAX_BLINK_RATE_PER_MINUTE   = 50    # above this = nervous/suspicious

# ── Behavioral Biometrics ──────────────────────
KEYSTROKE_BASELINE_SECONDS  = 120   # build baseline for first 2 minutes
KEYSTROKE_ANOMALY_THRESHOLD = 2.5   # flag if deviation > 2.5x baseline avg
PASTE_CHAR_THRESHOLD        = 100   # flag paste if more than 100 chars
MOUSE_SAMPLE_INTERVAL_MS    = 100   # sample mouse position every 100ms
MOUSE_SPEED_THRESHOLD       = 3000  # pixels/sec — above this is suspicious

# ── Audio ──────────────────────────────────────
AUDIO_SAMPLE_RATE           = 16000
AUDIO_CHUNK_SIZE            = 1024
AUDIO_CHANNELS              = 1
SPEAKER_COUNT_THRESHOLD     = 1     # flag if more than 1 speaker detected
WHISPER_ENERGY_THRESHOLD    = 0.02  # low energy + voice = whisper
NOISE_ANOMALY_THRESHOLD     = 0.85  # sudden spike in audio energy

# ── Deepfake Detection ─────────────────────────
DEEPFAKE_CHECK_INTERVAL_SEC = 60    # run deepfake check every 60 seconds
DEEPFAKE_CONFIDENCE_THRESHOLD = 0.75 # flag if synthetic confidence > 0.75

# ── Temporal / LSTM ────────────────────────────
TEMPORAL_WINDOW_SIZE        = 60    # analyze last 60 events as a sequence
TEMPORAL_SUSPICIOUS_THRESHOLD = 0.80 # flag if LSTM confidence > 0.80

# ── Risk Scoring Weights ───────────────────────
# All weights must add up to 100
RISK_WEIGHTS = {
    "face_missing":       15,
    "multiple_faces":     15,
    "gaze_offscreen":     15,
    "head_pose":          10,
    "liveness_fail":      10,
    "biometric_anomaly":  10,
    "audio_anomaly":      10,
    "deepfake":           10,
    "temporal_pattern":    5,
}

# Risk level thresholds
RISK_LOW_MAX    = 39    # 0–39   = LOW
RISK_MEDIUM_MAX = 69    # 40–69  = MEDIUM
                        # 70–100 = HIGH

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