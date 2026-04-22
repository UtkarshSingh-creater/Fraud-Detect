# ProctorAI — Real-Time Interview Anti-Cheating Detection Engine

> An ML-powered proctoring engine that runs on the candidate's machine
> during live online interviews (Skype, Zoom, Teams) and detects
> cheating in real time using computer vision, audio analysis,
> and behavioral biometrics.

---

## Demo

[Link to demo video]

---

## What It Detects

| Module | What It Catches | Technology |
|---|---|---|
| Face Detection | Missing face, identity swap, multiple people | face-recognition, dlib |
| Gaze Tracking | Looking at corner (floating AI window), off-screen | MediaPipe FaceMesh |
| Head Pose | Looking at phone/notes left/right/up/down | OpenCV solvePnP |
| Liveness | Photo/video attack via blink rate + movement | MediaPipe EAR |
| Object Detection | Phone, book, laptop on desk | YOLOv8-nano |
| Keystroke Dynamics | Paste events, inhuman typing speed | pynput |
| Mouse Monitoring | Speed anomalies, rapid clicking | pynput |
| Window Monitor | App switching, browser opens, floating windows | AppKit/pywin32 |
| Audio Intelligence | Multiple speakers, whispering | PyAudio, webrtcvad |
| Deepfake Detection | Synthetic/AI-generated face | MobileNetV2 CNN |
| Temporal LSTM | Suspicious behavior patterns over time | PyTorch LSTM |
| Process Scanner | ChatGPT, Claude, Copilot running in background | psutil |

---

## Risk Score Output

Every detection sends a JSON payload over WebSocket to the backend:

```json
{
  "risk_score": 78,
  "risk_level": "HIGH",
  "confidence": 0.91,
  "session_id": "session_001",
  "trigger_event": "banned_object",
  "flagged_signals": ["gaze_offscreen", "banned_object", "audio_anomaly"],
  "timestamp": 1713456789.123
}
```

Risk levels:

| Score | Level |
|---|---|
| 0–30 | LOW |
| 31–60 | MEDIUM |
| 61–100 | HIGH |

---

## Architecture
Candidate's Machine
│
├── vision/
│   ├── face_detector.py      → face + identity
│   ├── gaze_tracker.py       → iris + gaze
│   ├── head_pose.py          → head angle
│   ├── liveness.py           → blink + movement
│   └── object_detector.py    → YOLOv8 banned objects
│
├── biometrics/
│   ├── keystroke.py          → typing + paste
│   ├── mouse.py              → mouse speed
│   └── window_monitor.py     → app switching
│
├── audio/
│   └── audio_monitor.py      → voice + whisper
│
├── ml_models/
│   ├── deepfake_detector.py  → real vs fake face
│   ├── temporal_analyzer.py  → LSTM pattern detection
│   └── train_temporal.py     → training script
│
├── scoring/
│   └── risk_engine.py        → weighted + smoothed score
│
├── websocket_client.py       → streams to backend
└── main.py                   → orchestrates everything
│
│ WebSocket JSON
▼
Backend (Django / FastAPI)
│
▼
Interviewer Dashboard
---

## Setup

### Requirements
- Python 3.11
- macOS or Windows
- Webcam + Microphone

### Installation

```bash
git clone https://github.com/UtkarshSingh-creater/Fraud-Detect.git
cd Fraud-Detect/FraudDetect/proctorAI
python -m venv venv
source venv/bin/activate        # macOS
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### macOS Extra Setup
```bash
brew install cmake portaudio boost
pip install pyobjc-framework-Cocoa
```

### Windows Extra Setup
```bash
pip install pywin32
```

### macOS Permissions Required
- System Settings → Privacy & Security → **Camera** → add Terminal
- System Settings → Privacy & Security → **Microphone** → add Terminal
- System Settings → Privacy & Security → **Input Monitoring** → add Terminal

### Environment Config
```bash
cp .env.example .env
# Edit .env — set WEBSOCKET_URL and SESSION_ID
```

### Run
```bash
# From repo root, just type:
proctorai

# Or manually:
cd FraudDetect/proctorAI
python main.py
```

---

## How It Works

### Session Flow
Baseline face capture (2 seconds)
↓
Calibration phase (10 seconds)
— learns neutral head pose and gaze center
↓
Live detection starts
— all modules run simultaneously
— risk score updated in real time
↓
Events stream to backend via WebSocket
↓
Session report on exit
### Calibration
The system spends 10 seconds learning your natural head position and gaze center before flagging anything. This eliminates false positives from people who naturally tilt their head or have asymmetric gaze.

### Temporal Smoothing
The risk score uses exponential smoothing:
- **Rising fast** — 60% weight on new signal (quick response to threats)
- **Falling slow** — 7% decay per update (past behavior counts)

This prevents score from jumping wildly on single frames.

---

## Backend Integration

The backend team needs to expose:
ws://your-server/ws/agent/{session_id}
Start a session with a specific ID:
```bash
SESSION_ID=interview_rahul_2026_04_18 proctorai
```

---

## Training the LSTM

The temporal LSTM is pre-trained on synthetic data:
```bash
cd FraudDetect/proctorAI
python ml_models/train_temporal.py
```

Trained weights are saved to `ml_models/weights/temporal_lstm.pth`.

---

## Built With

- **Computer Vision**: OpenCV, MediaPipe, face-recognition, dlib
- **Object Detection**: YOLOv8-nano (Ultralytics)
- **ML / Deep Learning**: PyTorch, MobileNetV2, LSTM
- **Audio**: PyAudio, librosa, webrtcvad
- **Behavioral**: pynput, psutil
- **Streaming**: websockets
- **Platform**: pyobjc (macOS), pywin32 (Windows)