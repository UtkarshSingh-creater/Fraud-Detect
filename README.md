# Fraud-Detect# ProctorAI Detection Engine
# ProctorAI — Real-Time Interview Anti-Cheating Engine

A Python-based ML detection engine that runs on the candidate's machine
during live online interviews and streams cheating signals to a backend
in real time over WebSocket.

---

## What It Detects

| Module | Detects |
|---|---|
| Face Detection | Missing face, multiple faces, identity swap |
| Gaze Tracking | Off-screen gaze, gaze locked to corner (floating AI window) |
| Head Pose | Abnormal head turns (looking at phone/notes) |
| Liveness | Blink rate, micro-movement (photo/video attack) |
| Object Detection | Phone, book, laptop via YOLOv8-nano |
| Keystroke Dynamics | Paste events, inhuman typing speed |
| Mouse Monitoring | Speed anomalies, rapid clicking |
| Window Monitor | App switching, banned apps opened |
| Audio Intelligence | Multiple speakers, whispering, noise anomalies |
| Deepfake Detection | Synthetic face via MobileNetV2 CNN |
| Temporal LSTM | Suspicious event sequence patterns |
| Process Scanner | ChatGPT, Claude, Copilot running in background |

---

## Output — What the Backend Receives

Every event sends a JSON payload over WebSocket:

```json
{
  "risk_score": 78,
  "risk_level": "HIGH",
  "confidence": 0.91,
  "session_id": "session_001",
  "trigger_event": "banned_object",
  "flagged_signals": ["gaze_offscreen", "banned_object", "audio_anomaly"],
  "breakdown": {
    "gaze_offscreen":  { "weight": 10, "flagged": true,  "severity": 0.9 },
    "banned_object":   { "weight": 15, "flagged": true,  "severity": 1.0 },
    "audio_anomaly":   { "weight": 5,  "flagged": true,  "severity": 0.7 }
  },
  "events": [...],
  "timestamp": 1713456789.123
}
```

---

## Project Structure
proctorAI/
├── main.py                        ← entry point — run this
├── config.py                      ← all thresholds and settings
├── websocket_client.py            ← streams events to backend
├── .env                           ← your credentials (never commit)
├── .env.example                   ← template for backend team
├── requirements.txt               ← all dependencies
│
├── vision/
│   ├── face_detector.py           ← face detection + recognition
│   ├── gaze_tracker.py            ← iris + gaze tracking
│   ├── head_pose.py               ← head angle estimation
│   ├── liveness.py                ← blink + movement detection
│   └── object_detector.py         ← YOLOv8 banned object detection
│
├── biometrics/
│   ├── keystroke.py               ← keystroke dynamics + paste
│   ├── mouse.py                   ← mouse speed + click patterns
│   └── window_monitor.py          ← app/window switch detection
│
├── audio/
│   └── audio_monitor.py           ← voice + whisper + noise
│
├── ml_models/
│   ├── deepfake_detector.py       ← MobileNetV2 real vs fake
│   ├── temporal_analyzer.py       ← LSTM suspicious pattern detection
│   ├── train_temporal.py          ← training script
│   └── weights/
│       └── temporal_lstm.pth      ← trained LSTM weights
│
├── scoring/
│   └── risk_engine.py             ← combines all signals → risk score
│
└── tests/                         ← individual module tests
├── test_face_detector.py
├── test_gaze_tracker.py
├── test_head_pose.py
├── test_liveness.py
├── test_keystroke.py
├── test_mouse.py
├── test_audio.py
├── test_deepfake.py
├── test_temporal.py
├── test_risk_engine.py
├── test_object_detector.py
├── test_window_monitor.py
└── test_websocket_client.py

---

## Setup

### 1. Clone and create virtual environment
```bash
git clone https://github.com/UtkarshSingh-creater/Fraud-Detect.git
cd Fraud-Detect/FraudDetect/proctorAI
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. macOS extra dependencies
```bash
brew install cmake portaudio boost
pip install pyobjc-framework-Cocoa
```

### 4. Windows extra dependencies
```bash
pip install pywin32
```

### 5. Configure environment
```bash
cp .env.example .env
# Edit .env and set WEBSOCKET_URL and SESSION_ID
```

### 6. Grant macOS permissions
- System Settings → Privacy & Security → Camera → add Terminal
- System Settings → Privacy & Security → Microphone → add Terminal
- System Settings → Privacy & Security → Input Monitoring → add Terminal

### 7. Run
```bash
cd FraudDetect/proctorAI
python main.py
```

---

## Backend Integration

### WebSocket endpoint the backend must expose:
ws://your-server/ws/agent/{session_id}

### Starting a session
The backend generates a `session_id` and passes it to the engine via `.env`:
```bash
SESSION_ID=interview_rahul_2024_04_18 python main.py
```

### Risk levels
| Score | Level |
|---|---|
| 0–39 | LOW |
| 40–69 | MEDIUM |
| 70–100 | HIGH |

---

## Tuning

All detection thresholds are in `config.py`. Key ones:

| Setting | Default | Effect |
|---|---|---|
| `GAZE_LOCK_SECONDS` | 2 | Seconds before gaze lock flags |
| `PASTE_CHAR_THRESHOLD` | 80 | Characters before paste flags |
| `HEAD_POSE_ALERT_COUNT` | 2 | Consecutive violations before flag |
| `OBJECT_CONFIDENCE_THRESHOLD` | 0.35 | YOLO detection confidence |
| `TEMPORAL_SUSPICIOUS_THRESHOLD` | 0.80 | LSTM suspicion threshold |

---

## macOS Permission Issues

If you see a SIGTRAP crash on startup:
1. Quit Terminal completely
2. Grant Input Monitoring + Microphone in System Settings
3. Reopen Terminal and run again

---

## Built With

- OpenCV, MediaPipe, face-recognition, dlib
- PyTorch, torchvision, ultralytics (YOLOv8)
- PyAudio, librosa, webrtcvad
- pynput, psutil, websockets
- pyobjc (macOS), pywin32 (Windows)