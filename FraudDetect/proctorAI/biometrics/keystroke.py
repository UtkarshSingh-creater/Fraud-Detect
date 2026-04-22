# ─────────────────────────────────────────────────────
# biometrics/keystroke.py
# Module 6a — Keystroke Dynamics
# Tracks typing rhythm, detects paste events & anomalies
# ─────────────────────────────────────────────────────

import time
import threading
from pynput import keyboard
from config import (
    KEYSTROKE_BASELINE_SECONDS,
    KEYSTROKE_ANOMALY_THRESHOLD,
    PASTE_CHAR_THRESHOLD,
)


class KeystrokeMonitor:
    def __init__(self, event_callback):
        """
        event_callback: function that receives events
        e.g. def on_event(event): send_to_backend(event)
        """
        self.event_callback   = event_callback

        # Timing
        self.last_key_time    = None
        self.session_start    = time.time()

        # Baseline building (first N seconds)
        self.baseline_gaps    = []   # keystroke gaps during baseline period
        self.baseline_avg     = None # computed after baseline period
        self.baseline_ready   = False

        # Stats
        self.all_gaps         = []
        self.paste_count      = 0
        self.total_keystrokes = 0

        # Clipboard paste tracking
        self.ctrl_pressed     = False
        self.cmd_pressed      = False

        # Listener (runs in background thread)
        self.listener         = None

    # ── Start monitoring ─────────────────────────────────────────────────
    def start(self):
        """Start keystroke monitoring in background thread."""
        self.listener = keyboard.Listener(
            on_press   = self._on_press,
            on_release = self._on_release,
        )
        self.listener.daemon = True
        self.listener.start()
        print("[KeystrokeMonitor] Started — monitoring keystrokes")

        # Schedule baseline computation
        threading.Timer(
            KEYSTROKE_BASELINE_SECONDS,
            self._compute_baseline
        ).start()

    # ── Stop monitoring ──────────────────────────────────────────────────
    def stop(self):
        if self.listener:
            self.listener.stop()
            print("[KeystrokeMonitor] Stopped")

    # ── Key press handler ────────────────────────────────────────────────
    def _on_press(self, key):
        now = time.time()

        # Track modifier keys for paste detection
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        if key == keyboard.Key.cmd:
            self.cmd_pressed = True

        # ── Detect Ctrl+V or Cmd+V (paste) ───────────────────────────
        try:
            if key.char == 'v' and (self.ctrl_pressed or self.cmd_pressed):
                self._handle_paste()
                return
        except AttributeError:
            pass

        # ── Measure keystroke gap ─────────────────────────────────────
        if self.last_key_time is not None:
            gap_ms = int((now - self.last_key_time) * 1000)

            # Gap under 20ms = impossible for human = paste/auto-fill
            if gap_ms < 20 and gap_ms > 0:
                self._send_event({
                    "type":     "keystroke",
                    "gap_ms":   gap_ms,
                    "flagged":  True,
                    "reason":   "inhuman_speed",
                    "message":  f"Keystroke gap {gap_ms}ms — impossible for human typing",
                    "timestamp": now,
                })
            else:
                # Normal keystroke — add to gaps
                self.all_gaps.append(gap_ms)

                # Add to baseline if still in baseline period
                elapsed = now - self.session_start
                if elapsed < KEYSTROKE_BASELINE_SECONDS:
                    self.baseline_gaps.append(gap_ms)

                # Check for anomaly against baseline
                flagged = False
                message = "Keystroke normal"
                if self.baseline_ready and self.baseline_avg:
                    deviation = gap_ms / self.baseline_avg
                    if deviation > KEYSTROKE_ANOMALY_THRESHOLD:
                        flagged = True
                        message = f"Typing speed anomaly — {deviation:.1f}x slower than baseline"
                    elif deviation < (1 / KEYSTROKE_ANOMALY_THRESHOLD):
                        flagged = True
                        message = f"Typing speed anomaly — {deviation:.1f}x faster than baseline"

                self._send_event({
                    "type":      "keystroke",
                    "gap_ms":    gap_ms,
                    "flagged":   flagged,
                    "baseline":  round(self.baseline_avg, 1) if self.baseline_avg else None,
                    "message":   message,
                    "timestamp": now,
                })

        self.last_key_time     = now
        self.total_keystrokes += 1

    # ── Key release handler ──────────────────────────────────────────────
    def _on_release(self, key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        if key == keyboard.Key.cmd:
            self.cmd_pressed = False

    # ── Handle paste event ───────────────────────────────────────────────
    def _handle_paste(self):
        """
        Called when Ctrl+V or Cmd+V is detected.
        Tries to measure clipboard size.
        """
        self.paste_count += 1
        char_count = self._get_clipboard_size()
        flagged    = char_count > PASTE_CHAR_THRESHOLD

        self._send_event({
            "type":       "paste",
            "char_count": char_count,
            "flagged":    flagged,
            "paste_count": self.paste_count,
            "message":    (
                f"Large paste detected — {char_count} characters"
                if flagged else
                f"Small paste — {char_count} characters"
            ),
            "timestamp":  time.time(),
        })

    # ── Get clipboard size ───────────────────────────────────────────────
    def _get_clipboard_size(self):
        """Returns number of characters currently in clipboard."""
        try:
            import subprocess
            result = subprocess.run(
                ["pbpaste"],   # macOS clipboard command
                capture_output = True,
                text           = True,
            )
            return len(result.stdout)
        except Exception:
            return 0

    # ── Compute baseline after N seconds ─────────────────────────────────
    def _compute_baseline(self):
        if len(self.baseline_gaps) >= 10:
            self.baseline_avg   = sum(self.baseline_gaps) / len(self.baseline_gaps)
            self.baseline_ready = True
            print(f"[KeystrokeMonitor] Baseline computed: {self.baseline_avg:.1f}ms avg gap")
        else:
            print("[KeystrokeMonitor] Not enough keystrokes for baseline — will retry")

    # ── Get current stats ────────────────────────────────────────────────
    def get_stats(self):
        return {
            "total_keystrokes": self.total_keystrokes,
            "paste_count":      self.paste_count,
            "baseline_avg_ms":  round(self.baseline_avg, 1) if self.baseline_avg else None,
            "baseline_ready":   self.baseline_ready,
        }

    # ── Send event via callback ──────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[KeystrokeMonitor] Callback error: {e}")