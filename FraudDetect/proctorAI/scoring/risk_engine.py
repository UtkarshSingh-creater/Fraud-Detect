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
            "banned_object":     {"flagged": False, "severity": 0.0, "count": 0},
            "tab_switch":        {"flagged": False, "severity": 0.0, "count": 0},
            "mouse_anomaly":     {"flagged": False, "severity": 0.0, "count": 0},
        }

        self.smoothed_score  = 0.0   # exponentially smoothed score
        self.peak_score      = 0     # highest score in session

        # ── Event log ─────────────────────────────────────────────────
        self.events          = []
        self.session_start   = time.time()

        # ── Score history ─────────────────────────────────────────────
        self.score_history   = []
        self.current_score   = 0
        self.current_level   = "LOW"
        self.confidence      = 0.0
        self.peak_score      = 0

        # ── Sustained flag tracking (drives escalation multiplier) ────
        # signal_flag_start   : wall-clock time when signal became continuously flagged
        # signal_last_flagged : wall-clock time of last flagged event (for grace period)
        self.signal_flag_start   = {k: None for k in self.signals}
        self.signal_last_flagged = {k: 0.0  for k in self.signals}

        # ── Session peak score (never decreases — survives live-score decay) ──
        self.session_peak_score  = 0

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

        # Temporal smoothing — score rises fast, falls slowly
        if score > self.smoothed_score:
            # Rising — react quickly to new threats
            self.smoothed_score = 0.4 * self.smoothed_score + 0.6 * score
        else:
            # Falling — decay slowly so past behavior counts
            self.smoothed_score = 0.93 * self.smoothed_score + 0.07 * score

        smoothed = min(round(self.smoothed_score), 100)

        self.current_score = smoothed
        self.current_level = self._classify(smoothed)
        self.confidence    = confidence

        if smoothed > self.peak_score:
            self.peak_score = smoothed

        if score > self.peak_score:
            self.peak_score = score

        # Track the highest score seen this session (survives live-score decay)
        if score > self.session_peak_score:
            self.session_peak_score = score

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
            "mouse_move":     "mouse_anomaly",
            "mouse_click":    "mouse_anomaly", 
            "audio":          "audio_anomaly",
            "deepfake":       "deepfake",
            "temporal":       "temporal_pattern",
            "banned_object":  "banned_object",
            "tab_switch":     "tab_switch",
        }

        signal_key = mapping.get(event_type)
        if not signal_key:
            return

        signal = self.signals[signal_key]

        if flagged:
            signal["count"]   += 1
            signal["flagged"]  = True
            signal["severity"] = self._get_severity(event_type, event)
            # Track the wall-clock of this flagged event
            self.signal_last_flagged[signal_key] = time.time()
            # Start the sustained timer only on the very first flag of a run
            if self.signal_flag_start[signal_key] is None:
                self.signal_flag_start[signal_key] = time.time()
        else:
            # Grace period: keep the sustained timer alive if last flag was recent
            since_last = time.time() - self.signal_last_flagged.get(signal_key, 0.0)
            if since_last > 17.0:
                self.signal_flag_start[signal_key] = None
            # Decay severity so score recovers when behaviour improves
            signal["severity"] = max(0.0, signal["severity"] - 0.01)
            if signal["severity"] == 0.0:
                signal["flagged"] = False

    # ── Compute weighted risk score ───────────────────────────────────────
    def _compute_score(self):
        total     = 0.0
        breakdown = {}
        now       = time.time()

        for signal_key, weight in RISK_WEIGHTS.items():
            signal        = self.signals[signal_key]
            sustained_s   = 0.0
            sustained_x   = 1.0
            time_factor   = 0.0
            contrib       = 0.0

            if signal["flagged"]:
                time_since_last = now - self.signal_last_flagged.get(signal_key, 0.0)

                if time_since_last > 17.0:
                    # No flagged events for 8 s → auto-clear this signal entirely.
                    # Handles modules (e.g. ObjectDetector) that never fire
                    # flagged=False cleanup events when the thing disappears.
                    signal["flagged"]  = False
                    signal["severity"] = 0.0
                    self.signal_flag_start[signal_key] = None
                else:
                    # Time-decay factor:
                    #   0.0 – 1.0 s : full contribution (grace window)
                    #                 covers brief face-flicker / YOLO miss-frames
                    #   1.0 – 6.0 s : fades linearly 1.0 → 0.0
                    #   > 8.0 s     : signal auto-cleared above
                    GRACE  = 2.0   # seconds — no decay within this window
                    WINDOW = 15.0   # seconds — linear fade after grace
                    if time_since_last <= GRACE:
                        time_factor = 1.0
                    else:
                        time_factor = max(0.0, 1.0 - (time_since_last - GRACE) / WINDOW)

                    # Sustained-escalation multiplier: only active while events
                    # are arriving (within the grace window). Drops to 1× the
                    # moment the signal stops firing so stale runs don't inflate
                    # the score.
                    if time_since_last <= GRACE:
                        flag_start  = self.signal_flag_start.get(signal_key)
                        sustained_s = (now - flag_start) if flag_start else 0.0
                        sustained_x = 1.0 + min(sustained_s / 2.0, 1.0)

                    contrib = weight * signal["severity"] * sustained_x * time_factor

            total += contrib
            breakdown[signal_key] = {
                "weight":      weight,
                "flagged":     signal["flagged"],
                "severity":    round(signal["severity"], 3),
                "contrib":     round(contrib, 2),
                "count":       signal["count"],
                "sustained_s": round(sustained_s, 1),
                "sustained_x": round(sustained_x, 2),
                "time_factor": round(time_factor, 2),
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
        if event_type == "tab_switch":
            return 1.0   # always high — any app switch during interview is suspicious

        if event_type == "paste":
            chars = event.get("char_count", 0)
            return min(chars / 500.0, 1.0)

        if event_type == "gaze":
            if event.get("gaze_locked") and event.get("is_offscreen"):
                return 1.0
            if event.get("gaze_locked"):
                return 0.8
            if event.get("is_offscreen"):
                return 0.7
            return 0.2

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
            yaw_f   = event.get("yaw_flagged",   False)
            pitch_f = event.get("pitch_flagged", False)
            if yaw_f and pitch_f:
                return 1.0
            if yaw_f or pitch_f:
                return 0.85
            return 0.4

        if event_type == "face_verify":
            return 0.0 if event.get("same_person", True) else 1.0

        if event_type == "banned_object":
            # Severity based on how dangerous the object is
            label = event.get("label", "")
            conf  = event.get("confidence", 0.5)
            if label == "cell phone":
                return min(0.85 + conf * 0.15, 1.0)   # highest — direct cheating tool
            if label == "laptop":
                return min(0.70 + conf * 0.15, 1.0)   # second device
            if label == "book":
                return min(0.55 + conf * 0.15, 1.0)   # notes / reference material
            return conf

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
            "risk_score": self.current_score,
            "risk_level": self.current_level,
            "confidence": confidence,
            "peak_score": self.peak_score,
            "session_peak_score": self.session_peak_score,
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
        self.events              = []
        self.score_history       = []
        self.session_start       = time.time()
        self.session_peak_score  = 0
        self.signal_flag_start   = {k: None for k in self.signals}
        self.signal_last_flagged = {k: 0.0  for k in self.signals}
        print("[RiskEngine] Session reset")

    # ── Send event via callback ───────────────────────────────────────────
    def _send_event(self, output):
        try:
            self.event_callback(output)
        except Exception as e:
            print(f"[RiskEngine] Callback error: {e}")