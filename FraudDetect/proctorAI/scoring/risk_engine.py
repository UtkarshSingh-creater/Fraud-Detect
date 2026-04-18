# ─────────────────────────────────────────────────────
# scoring/risk_engine.py
# Module 10 — Risk Scoring Engine
# Combines all module signals into a final risk score
# ─────────────────────────────────────────────────────

import time
from config import (
    RISK_WEIGHTS,
    RISK_LOW_MAX,
    RISK_MEDIUM_MAX,
)


class RiskEngine:
    def __init__(self, event_callback=None):
        """
        event_callback: function that receives final risk score events
                        to send to backend
        """
        self.event_callback = event_callback

        # ── Latest signal state from each module ──────────────────────
        self.signals = {
            "face_missing":      {"flagged": False, "severity": 0.0, "count": 0},
            "multiple_faces":    {"flagged": False, "severity": 0.0, "count": 0},
            "gaze_offscreen":    {"flagged": False, "severity": 0.0, "count": 0},
            "head_pose":         {"flagged": False, "severity": 0.0, "count": 0},
            "liveness_fail":     {"flagged": False, "severity": 0.0, "count": 0},
            "biometric_anomaly": {"flagged": False, "severity": 0.0, "count": 0},
            "audio_anomaly":     {"flagged": False, "severity": 0.0, "count": 0},
            "deepfake":          {"flagged": False, "severity": 0.0, "count": 0},
            "temporal_pattern":  {"flagged": False, "severity": 0.0, "count": 0},
        }

        # ── Event log ─────────────────────────────────────────────────
        self.events          = []
        self.session_start   = time.time()

        # ── Score history ─────────────────────────────────────────────
        self.score_history   = []
        self.current_score   = 0
        self.current_level   = "LOW"
        self.confidence      = 0.0

    # ── Ingest event from any module ────────────────────────────────────
    def process_event(self, event):
        """
        Call this with every event from every module.
        Updates internal signal state and recomputes risk score.
        Returns updated risk output.
        """
        event_type = event.get("type", "")
        flagged    = event.get("flagged", False)

        # ── Map event type to signal ──────────────────────────────────
        self._update_signal(event_type, event, flagged)

        # ── Append to event log ───────────────────────────────────────
        self.events.append({
            **event,
            "ingested_at": time.time(),
        })

        # Keep only last 200 events in memory
        if len(self.events) > 200:
            self.events.pop(0)

        # ── Recompute risk score ──────────────────────────────────────
        score, breakdown = self._compute_score()
        level            = self._classify(score)
        confidence       = self._compute_confidence()

        self.current_score = score
        self.current_level = level
        self.confidence    = confidence
        self.score_history.append({"score": score, "timestamp": time.time()})

        # Keep only last 100 score snapshots
        if len(self.score_history) > 100:
            self.score_history.pop(0)

        # ── Build output ──────────────────────────────────────────────
        output = self._build_output(score, level, confidence, breakdown, event)

        # ── Send to backend via callback ──────────────────────────────
        if self.event_callback and flagged:
            self._send_event(output)

        return output

    # ── Update signal state based on event type ──────────────────────────
    def _update_signal(self, event_type, event, flagged):
        mapping = {
            "face_missing":   "face_missing",
            "multiple_faces": "multiple_faces",
            "face_verify":    "face_missing",
            "gaze":           "gaze_offscreen",
            "head_pose":      "head_pose",
            "liveness":       "liveness_fail",
            "keystroke":      "biometric_anomaly",
            "paste":          "biometric_anomaly",
            "mouse_move":     "biometric_anomaly",
            "mouse_click":    "biometric_anomaly",
            "audio":          "audio_anomaly",
            "deepfake":       "deepfake",
            "temporal":       "temporal_pattern",
        }

        signal_key = mapping.get(event_type)
        if not signal_key:
            return

        signal = self.signals[signal_key]

        if flagged:
            signal["count"]   += 1
            signal["flagged"]  = True
            signal["severity"] = self._get_severity(event_type, event)
        else:
            # Decay severity slightly when not flagged
            signal["severity"] = max(0.0, signal["severity"] - 0.05)
            if signal["severity"] == 0.0:
                signal["flagged"] = False

    # ── Compute weighted risk score ───────────────────────────────────────
    def _compute_score(self):
        total     = 0.0
        breakdown = {}

        for signal_key, weight in RISK_WEIGHTS.items():
            signal    = self.signals[signal_key]
            # Score = weight * severity (if flagged)
            # Severity decays when not flagged
            contrib   = weight * signal["severity"] if signal["flagged"] else 0.0
            total    += contrib
            breakdown[signal_key] = {
                "weight":    weight,
                "flagged":   signal["flagged"],
                "severity":  round(signal["severity"], 3),
                "contrib":   round(contrib, 2),
                "count":     signal["count"],
            }

        return min(round(total), 100), breakdown

    # ── Classify risk level ───────────────────────────────────────────────
    def _classify(self, score):
        if score <= RISK_LOW_MAX:
            return "LOW"
        elif score <= RISK_MEDIUM_MAX:
            return "MEDIUM"
        return "HIGH"

    # ── Compute confidence based on number of signals active ─────────────
    def _compute_confidence(self):
        """
        Confidence increases as more independent signals agree.
        One signal firing = low confidence.
        Multiple signals firing = high confidence.
        """
        active_signals = sum(
            1 for s in self.signals.values() if s["flagged"]
        )
        total_signals  = len(self.signals)

        # Confidence formula — more signals = more confident
        base_confidence = active_signals / total_signals
        # Boost confidence if same signal fired multiple times
        repeat_boost    = min(
            sum(s["count"] for s in self.signals.values() if s["flagged"]) / 20.0,
            0.3,
        )
        return round(min(base_confidence + repeat_boost, 1.0), 2)

    # ── Get severity for specific event types ─────────────────────────────
    def _get_severity(self, event_type, event):
        if event_type == "paste":
            chars = event.get("char_count", 0)
            return min(chars / 500.0, 1.0)

        if event_type == "gaze":
            return 0.9 if event.get("gaze_locked") else 0.5

        if event_type == "audio":
            if event.get("multiple_speakers"):
                return 0.9
            if event.get("whisper_detected"):
                return 0.6
            return 0.3

        if event_type == "deepfake":
            return event.get("fake_prob", 0.5)

        if event_type == "temporal":
            return event.get("suspicious_prob", 0.5)

        if event_type == "face_missing":
            duration = event.get("duration", 3)
            return min(duration / 10.0, 1.0)

        if event_type == "multiple_faces":
            return 0.9

        if event_type == "liveness":
            return 0.8 if not event.get("is_live") else 0.0

        if event_type == "keystroke":
            gap = event.get("gap_ms", 100)
            return 1.0 if gap < 20 else 0.3

        if event_type in ("mouse_move", "mouse_click"):
            return 0.4

        if event_type == "head_pose":
            return 0.6

        if event_type == "face_verify":
            return 0.0 if event.get("same_person", True) else 1.0

        return 0.5

    # ── Build final output dict ───────────────────────────────────────────
    def _build_output(self, score, level, confidence, breakdown, trigger_event):
        elapsed = round(time.time() - self.session_start, 1)

        return {
            "type":            "risk_score",
            "risk_score":      score,
            "risk_level":      level,
            "confidence":      confidence,
            "session_elapsed": elapsed,
            "trigger_event":   trigger_event.get("type"),
            "breakdown":       breakdown,
            "flagged_signals": [
                k for k, v in self.signals.items() if v["flagged"]
            ],
            "events":          self.events[-10:],  # last 10 events
            "timestamp":       time.time(),
        }

    # ── Get current snapshot ──────────────────────────────────────────────
    def get_snapshot(self):
        """
        Call anytime to get current risk state
        without needing a new event.
        """
        score, breakdown = self._compute_score()
        level            = self._classify(score)
        confidence       = self._compute_confidence()

        return {
            "risk_score":      score,
            "risk_level":      level,
            "confidence":      confidence,
            "flagged_signals": [
                k for k, v in self.signals.items() if v["flagged"]
            ],
            "signal_counts":   {
                k: v["count"] for k, v in self.signals.items()
            },
            "total_events":    len(self.events),
            "session_elapsed": round(time.time() - self.session_start, 1),
            "score_history":   self.score_history[-10:],
        }

    # ── Reset session ─────────────────────────────────────────────────────
    def reset(self):
        for signal in self.signals.values():
            signal["flagged"]  = False
            signal["severity"] = 0.0
            signal["count"]    = 0
        self.events        = []
        self.score_history = []
        self.session_start = time.time()
        print("[RiskEngine] Session reset")

    # ── Send event via callback ───────────────────────────────────────────
    def _send_event(self, output):
        try:
            self.event_callback(output)
        except Exception as e:
            print(f"[RiskEngine] Callback error: {e}")