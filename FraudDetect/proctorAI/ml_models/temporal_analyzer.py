# ─────────────────────────────────────────────────────
# ml_models/temporal_analyzer.py
# Module 9 — Temporal Pattern Analysis
# LSTM model that detects suspicious event sequences
# ─────────────────────────────────────────────────────

import time
import threading
import numpy as np
import torch
import torch.nn as nn
from config import (
    TEMPORAL_WINDOW_SIZE,
    TEMPORAL_SUSPICIOUS_THRESHOLD,
)


# ── Event type to integer mapping ───────────────────────────────────────
EVENT_TYPE_MAP = {
    "gaze":         0,
    "face_missing": 1,
    "face_verify":  2,
    "multiple_faces": 3,
    "head_pose":    4,
    "liveness":     5,
    "keystroke":    6,
    "paste":        7,
    "mouse_move":   8,
    "mouse_click":  9,
    "audio":        10,
    "deepfake":     11,
    "tab_switch":   12,
    "process":      13,
}

INPUT_SIZE  = 3   # [event_type_normalized, flagged, severity]
HIDDEN_SIZE = 64
NUM_LAYERS  = 2
OUTPUT_SIZE = 1   # suspicious probability 0.0 to 1.0


# ── LSTM Model Definition ────────────────────────────────────────────────
class SuspiciousPatternLSTM(nn.Module):
    def __init__(self):
        super(SuspiciousPatternLSTM, self).__init__()

        self.lstm = nn.LSTM(
            input_size   = INPUT_SIZE,
            hidden_size  = HIDDEN_SIZE,
            num_layers   = NUM_LAYERS,
            batch_first  = True,
            dropout      = 0.2,
        )
        self.classifier = nn.Sequential(
            nn.Linear(HIDDEN_SIZE, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, OUTPUT_SIZE),
            nn.Sigmoid(),
        )

    def forward(self, x):
        lstm_out, _  = self.lstm(x)
        last_hidden  = lstm_out[:, -1, :]   # take last timestep
        out          = self.classifier(last_hidden)
        return out


# ── Temporal Analyzer ────────────────────────────────────────────────────
class TemporalAnalyzer:
    def __init__(self, event_callback, weights_path=None):
        """
        event_callback : function that receives events
        weights_path   : path to trained LSTM weights
                         if None, uses random weights (for testing)
        """
        self.event_callback  = event_callback
        self.weights_path    = weights_path
        self.window_size     = TEMPORAL_WINDOW_SIZE
        self.event_buffer    = []   # rolling window of last N events
        self.last_check_time = 0
        self.check_interval  = 10.0  # analyze every 10 seconds
        self.is_running      = False

        # Stats
        self.total_analyses  = 0
        self.suspicious_count = 0

        # ── Build model ───────────────────────────────────────────────
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model  = self._build_model()

        print(f"[TemporalAnalyzer] Initialized on {self.device}")

    # ── Build LSTM model ─────────────────────────────────────────────────
    def _build_model(self):
        model = SuspiciousPatternLSTM().to(self.device)

        if self.weights_path:
            try:
                state = torch.load(self.weights_path, map_location=self.device)
                model.load_state_dict(state)
                print(f"[TemporalAnalyzer] Loaded weights from {self.weights_path}")
            except Exception as e:
                print(f"[TemporalAnalyzer] Could not load weights: {e} — using random weights")

        model.eval()
        return model

    # ── Start background analysis thread ─────────────────────────────────
    def start(self):
        self.is_running = True
        thread          = threading.Thread(target=self._analysis_loop, daemon=True)
        thread.start()
        print("[TemporalAnalyzer] Background analysis started")

    # ── Stop ─────────────────────────────────────────────────────────────
    def stop(self):
        self.is_running = False
        print("[TemporalAnalyzer] Stopped")

    # ── Add event to buffer (called from main orchestrator) ──────────────
    def add_event(self, event):
        """
        Call this every time any module produces an event.
        Keeps a rolling window of the last N events.
        """
        self.event_buffer.append(event)

        # Keep only last TEMPORAL_WINDOW_SIZE events
        if len(self.event_buffer) > self.window_size:
            self.event_buffer.pop(0)

    # ── Background analysis loop ──────────────────────────────────────────
    def _analysis_loop(self):
        while self.is_running:
            now = time.time()
            if (
                now - self.last_check_time >= self.check_interval and
                len(self.event_buffer) >= 10   # need at least 10 events
            ):
                self._run_analysis()
                self.last_check_time = now
            time.sleep(1.0)

    # ── Run LSTM analysis on current event buffer ─────────────────────────
    def _run_analysis(self):
        try:
            # ── Convert events to feature tensor ─────────────────────
            sequence = self._events_to_tensor(self.event_buffer)
            if sequence is None:
                return

            tensor = torch.FloatTensor(sequence).unsqueeze(0).to(self.device)

            # ── Run inference ─────────────────────────────────────────
            with torch.no_grad():
                suspicious_prob = float(self.model(tensor).squeeze())

            is_suspicious = suspicious_prob > TEMPORAL_SUSPICIOUS_THRESHOLD
            self.total_analyses += 1

            if is_suspicious:
                self.suspicious_count += 1

            # ── Identify which pattern triggered it ───────────────────
            pattern = self._identify_pattern()

            self._send_event({
                "type":             "temporal",
                "suspicious_prob":  round(suspicious_prob, 3),
                "is_suspicious":    is_suspicious,
                "flagged":          is_suspicious,
                "pattern":          pattern,
                "events_analyzed":  len(self.event_buffer),
                "message":          (
                    f"Suspicious pattern detected — {suspicious_prob:.1%} confidence: {pattern}"
                    if is_suspicious else
                    f"Event sequence normal — {suspicious_prob:.1%} suspicion"
                ),
                "timestamp":        time.time(),
            })

        except Exception as e:
            print(f"[TemporalAnalyzer] Analysis error: {e}")

    # ── Convert event list to numpy feature array ─────────────────────────
    def _events_to_tensor(self, events):
        """
        Each event becomes a 3-element feature vector:
        [event_type_normalized, is_flagged, severity]
        """
        if not events:
            return None

        features = []
        for event in events:
            event_type = EVENT_TYPE_MAP.get(event.get("type", ""), 0)
            flagged    = 1.0 if event.get("flagged", False) else 0.0
            severity   = self._get_severity(event)

            features.append([
                event_type / len(EVENT_TYPE_MAP),  # normalize to 0-1
                flagged,
                severity,
            ])

        # Pad or truncate to window size
        while len(features) < self.window_size:
            features.insert(0, [0.0, 0.0, 0.0])   # pad with zeros at start
        features = features[-self.window_size:]     # keep last N

        return np.array(features, dtype=np.float32)

    # ── Get severity score for an event ──────────────────────────────────
    def _get_severity(self, event):
        """
        Returns 0.0 to 1.0 severity based on event type and values.
        """
        t = event.get("type", "")

        if t == "paste":
            chars = event.get("char_count", 0)
            return min(chars / 1000.0, 1.0)

        if t == "gaze":
            return 0.8 if event.get("gaze_locked") else 0.3

        if t == "audio":
            return 0.9 if event.get("multiple_speakers") else (
                0.6 if event.get("whisper_detected") else 0.1
            )

        if t == "deepfake":
            return event.get("fake_prob", 0.0)

        if t == "face_missing":
            duration = event.get("duration", 0)
            return min(duration / 30.0, 1.0)

        if t == "multiple_faces":
            return 0.9

        if t == "process":
            return 1.0 if event.get("flagged") else 0.0

        if t == "keystroke":
            gap = event.get("gap_ms", 100)
            return 1.0 if gap < 20 else 0.1

        return 0.5 if event.get("flagged") else 0.1

    # ── Identify suspicious pattern from event buffer ─────────────────────
    def _identify_pattern(self):
        """
        Rule-based pattern identification on top of LSTM output.
        Returns human-readable pattern description.
        """
        if not self.event_buffer:
            return "unknown"

        flagged_types = [
            e.get("type") for e in self.event_buffer
            if e.get("flagged")
        ]

        # Count occurrences
        gaze_flags    = flagged_types.count("gaze")
        paste_flags   = flagged_types.count("paste")
        audio_flags   = flagged_types.count("audio")
        process_flags = flagged_types.count("process")
        face_flags    = (
            flagged_types.count("face_missing") +
            flagged_types.count("face_verify")
        )

        # Pattern matching
        if gaze_flags >= 3 and paste_flags >= 2:
            return "gaze-to-AI-then-paste cycle"
        if process_flags >= 1:
            return "banned AI process running"
        if audio_flags >= 3:
            return "sustained multiple voice activity"
        if paste_flags >= 3:
            return "repeated large paste events"
        if gaze_flags >= 5:
            return "persistent off-screen gaze"
        if face_flags >= 2:
            return "identity or face anomaly"

        return "general suspicious activity pattern"

    # ── Get stats ─────────────────────────────────────────────────────────
    def get_stats(self):
        return {
            "total_analyses":   self.total_analyses,
            "suspicious_count": self.suspicious_count,
            "buffer_size":      len(self.event_buffer),
        }

    # ── Send event via callback ───────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[TemporalAnalyzer] Callback error: {e}")