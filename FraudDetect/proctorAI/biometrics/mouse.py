# ─────────────────────────────────────────────────────
# biometrics/mouse.py
# Module 6b — Mouse Movement Patterns
# Tracks speed, acceleration, builds baseline, detects anomalies
# ─────────────────────────────────────────────────────

import time
import threading
import numpy as np
from pynput import mouse
from config import (
    KEYSTROKE_BASELINE_SECONDS,
    MOUSE_SAMPLE_INTERVAL_MS,
    MOUSE_SPEED_THRESHOLD,
)


class MouseMonitor:
    def __init__(self, event_callback):
        """
        event_callback: function that receives events
        e.g. def on_event(event): send_to_backend(event)
        """
        self.event_callback    = event_callback

        # Position tracking
        self.prev_x            = None
        self.prev_y            = None
        self.prev_time         = None

        # Speed history
        self.speed_samples     = []
        self.accel_samples     = []
        self.prev_speed        = 0.0

        # Baseline
        self.baseline_speeds   = []
        self.baseline_avg      = None
        self.baseline_ready    = False
        self.session_start     = time.time()

        # Click tracking
        self.click_count       = 0
        self.last_click_time   = None
        self.rapid_click_count = 0

        # Sample interval
        self.sample_interval   = MOUSE_SAMPLE_INTERVAL_MS / 1000.0
        self.last_sample_time  = 0

        # Listener
        self.listener          = None

    # ── Start monitoring ─────────────────────────────────────────────────
    def start(self):
        """Start mouse monitoring in background thread."""
        self.listener = mouse.Listener(
            on_move   = self._on_move,
            on_click  = self._on_click,
        )
        self.listener.daemon = True
        self.listener.start()
        print("[MouseMonitor] Started — monitoring mouse")

        # Schedule baseline computation
        threading.Timer(
            KEYSTROKE_BASELINE_SECONDS,
            self._compute_baseline,
        ).start()

    # ── Stop monitoring ──────────────────────────────────────────────────
    def stop(self):
        if self.listener:
            self.listener.stop()
            print("[MouseMonitor] Stopped")

    # ── Mouse move handler ───────────────────────────────────────────────
    def _on_move(self, x, y):
        now = time.time()

        # Throttle to sample interval
        if now - self.last_sample_time < self.sample_interval:
            return
        self.last_sample_time = now

        if self.prev_x is None:
            self.prev_x    = x
            self.prev_y    = y
            self.prev_time = now
            return

        # ── Calculate speed (pixels per second) ──────────────────────
        dt       = now - self.prev_time
        if dt == 0:
            return

        distance = np.sqrt((x - self.prev_x) ** 2 + (y - self.prev_y) ** 2)
        speed    = distance / dt  # pixels per second

        # ── Calculate acceleration ────────────────────────────────────
        accel    = (speed - self.prev_speed) / dt

        self.speed_samples.append(speed)
        self.accel_samples.append(accel)
        self.prev_speed = speed

        # Keep only last 200 samples
        if len(self.speed_samples) > 200:
            self.speed_samples.pop(0)
        if len(self.accel_samples) > 200:
            self.accel_samples.pop(0)

        # Add to baseline if still in baseline period
        elapsed = now - self.session_start
        if elapsed < KEYSTROKE_BASELINE_SECONDS:
            self.baseline_speeds.append(speed)

        # ── Check speed threshold ─────────────────────────────────────
        speed_flagged = speed > MOUSE_SPEED_THRESHOLD

        # ── Check anomaly against baseline ────────────────────────────
        anomaly_flagged = False
        anomaly_message = "Mouse movement normal"

        if self.baseline_ready and self.baseline_avg and self.baseline_avg > 0:
            deviation = speed / self.baseline_avg
            if deviation > 3.0:
                anomaly_flagged = True
                anomaly_message = f"Mouse speed anomaly — {deviation:.1f}x faster than baseline"
            elif deviation < 0.05 and speed > 50:
                anomaly_flagged = True
                anomaly_message = f"Mouse movement unusually slow — {deviation:.1f}x baseline"

        flagged = speed_flagged or anomaly_flagged
        message = anomaly_message if anomaly_flagged else (
            f"Mouse speed {int(speed)}px/s — too fast" if speed_flagged
            else "Mouse movement normal"
        )

        # Only send event if flagged or every 10 samples
        if flagged or len(self.speed_samples) % 10 == 0:
            self._send_event({
                "type":          "mouse_move",
                "x":             x,
                "y":             y,
                "speed":         round(speed, 1),
                "acceleration":  round(accel, 1),
                "flagged":       flagged,
                "message":       message,
                "timestamp":     now,
            })

        self.prev_x    = x
        self.prev_y    = y
        self.prev_time = now

    # ── Mouse click handler ──────────────────────────────────────────────
    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return

        now = time.time()
        self.click_count += 1

        # ── Detect rapid clicking ─────────────────────────────────────
        if self.last_click_time is not None:
            gap_ms = int((now - self.last_click_time) * 1000)
            if gap_ms < 200:   # clicks less than 200ms apart
                self.rapid_click_count += 1
                if self.rapid_click_count >= 3:
                    self._send_event({
                        "type":        "mouse_click",
                        "x":           x,
                        "y":           y,
                        "button":      str(button),
                        "gap_ms":      gap_ms,
                        "flagged":     True,
                        "message":     f"Rapid clicking detected — {gap_ms}ms between clicks",
                        "timestamp":   now,
                    })
            else:
                self.rapid_click_count = 0
                self._send_event({
                    "type":      "mouse_click",
                    "x":         x,
                    "y":         y,
                    "button":    str(button),
                    "gap_ms":    gap_ms,
                    "flagged":   False,
                    "message":   "Normal click",
                    "timestamp": now,
                })

        self.last_click_time = now

    # ── Compute baseline ─────────────────────────────────────────────────
    def _compute_baseline(self):
        if len(self.baseline_speeds) >= 20:
            self.baseline_avg   = float(np.mean(self.baseline_speeds))
            self.baseline_ready = True
            print(f"[MouseMonitor] Baseline computed: {self.baseline_avg:.1f}px/s avg speed")
        else:
            print("[MouseMonitor] Not enough mouse data for baseline — will retry")

    # ── Get current stats ────────────────────────────────────────────────
    def get_stats(self):
        return {
            "click_count":     self.click_count,
            "avg_speed":       round(float(np.mean(self.speed_samples)), 1) if self.speed_samples else 0,
            "max_speed":       round(float(np.max(self.speed_samples)), 1)  if self.speed_samples else 0,
            "baseline_avg":    round(self.baseline_avg, 1) if self.baseline_avg else None,
            "baseline_ready":  self.baseline_ready,
        }

    # ── Send event via callback ──────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[MouseMonitor] Callback error: {e}")