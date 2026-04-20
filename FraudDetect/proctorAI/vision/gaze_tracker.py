# ─────────────────────────────────────────────────────
# vision/gaze_tracker.py
# Module 3 — Eye Gaze Tracking
# Tracks iris position, detects off-screen looking
# ─────────────────────────────────────────────────────

import cv2
import mediapipe as mp
import numpy as np
import time
from config import (
    GAZE_OFFSCREEN_THRESHOLD_X,
    GAZE_OFFSCREEN_THRESHOLD_Y,
    GAZE_LOCK_SECONDS,
    GAZE_SEND_INTERVAL_MS,
)


class GazeTracker:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces        = 1,
            refine_landmarks     = True,   # enables iris landmarks
            min_detection_confidence = 0.5,
            min_tracking_confidence  = 0.5,
        )

        # Iris landmark indices from MediaPipe FaceMesh
        self.LEFT_IRIS  = [474, 475, 476, 477]
        self.RIGHT_IRIS = [469, 470, 471, 472]

        # Gaze history for lock detection
        self.gaze_history        = []   # list of (x, y, timestamp)
        self.last_send_time      = 0
        self.send_interval       = GAZE_SEND_INTERVAL_MS / 1000.0  # convert to seconds

        # Heatmap tracking (normalized 0.0 to 1.0)
        self.total_gaze_samples  = 0
        self.offscreen_samples   = 0

    # ── Main method: call on every frame ────────────────────────────────
    def process_frame(self, frame):
        """
        Call this on every webcam frame.
        Returns list of events to send to backend.
        """
        events = []
        h, w   = frame.shape[:2]
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.face_mesh.process(rgb)

        if not result.multi_face_landmarks:
            return events  # no face found, skip

        landmarks = result.multi_face_landmarks[0].landmark

        # ── Get iris center positions ────────────────────────────────
        left_iris  = self._get_iris_center(landmarks, self.LEFT_IRIS,  w, h)
        right_iris = self._get_iris_center(landmarks, self.RIGHT_IRIS, w, h)

        # Average both eyes for final gaze point
        gaze_x = (left_iris[0] + right_iris[0]) / 2.0
        gaze_y = (left_iris[1] + right_iris[1]) / 2.0

        # Normalize to 0.0 - 1.0
        norm_x = round(gaze_x / w, 3)
        norm_y = round(gaze_y / h, 3)

        # ── Track offscreen percentage ───────────────────────────────
        self.total_gaze_samples += 1
        # Apply calibration offset if available
        neutral_x = getattr(self, "_neutral_x", 0.5)
        neutral_y = getattr(self, "_neutral_y", 0.5)

        deviation_x = abs(norm_x - neutral_x)
        deviation_y = abs(norm_y - neutral_y)

        is_offscreen = (
            deviation_x > (GAZE_OFFSCREEN_THRESHOLD_X - 0.5) or
            deviation_y > (GAZE_OFFSCREEN_THRESHOLD_Y - 0.5)
        )
        if is_offscreen:
            self.offscreen_samples += 1

        offscreen_pct = round(
            (self.offscreen_samples / self.total_gaze_samples) * 100, 1
        ) if self.total_gaze_samples > 0 else 0.0

        # ── Add to history for gaze lock detection ───────────────────
        now = time.time()
        self.gaze_history.append((norm_x, norm_y, now))

        # Keep only last GAZE_LOCK_SECONDS worth of history
        self.gaze_history = [
            g for g in self.gaze_history
            if now - g[2] <= GAZE_LOCK_SECONDS
        ]

        # ── Check for gaze lock (staring at one spot) ────────────────
        gaze_locked = False
        if len(self.gaze_history) >= 10:
            xs = [g[0] for g in self.gaze_history]
            ys = [g[1] for g in self.gaze_history]
            x_variance = np.var(xs)
            y_variance = np.var(ys)
            # Very low variance = gaze not moving = locked onto something
            if x_variance < 0.0003 and y_variance < 0.0003:
                gaze_locked = True

        # ── Send event at defined interval ───────────────────────────
        if now - self.last_send_time >= self.send_interval:
            self.last_send_time = now
            events.append(self._make_event(
                "gaze",
                x               = norm_x,
                y               = norm_y,
                flagged         = is_offscreen or gaze_locked,
                is_offscreen    = is_offscreen,
                gaze_locked     = gaze_locked,
                offscreen_pct   = offscreen_pct,
                message         = self._get_message(is_offscreen, gaze_locked),
            ))

        return events

    # ── Draw gaze point on frame (debug only) ───────────────────────────
    def draw_debug(self, frame):
        """
        Draws iris points and gaze status on frame.
        Only use during development.
        """
        h, w   = frame.shape[:2]
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.face_mesh.process(rgb)

        if not result.multi_face_landmarks:
            return frame

        landmarks  = result.multi_face_landmarks[0].landmark
        left_iris  = self._get_iris_center(landmarks, self.LEFT_IRIS,  w, h)
        right_iris = self._get_iris_center(landmarks, self.RIGHT_IRIS, w, h)

        # Draw iris centers
        cv2.circle(frame, left_iris,  4, (0, 255, 255), -1)
        cv2.circle(frame, right_iris, 4, (0, 255, 255), -1)

        # Draw gaze average point
        avg_x = int((left_iris[0] + right_iris[0]) / 2)
        avg_y = int((left_iris[1] + right_iris[1]) / 2)
        cv2.circle(frame, (avg_x, avg_y), 6, (255, 0, 0), 2)

        # Show normalized coords
        norm_x = round(avg_x / w, 3)
        norm_y = round(avg_y / h, 3)
        cv2.putText(
            frame,
            f"Gaze: ({norm_x}, {norm_y})",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (0, 255, 255), 2,
        )

        return frame

    # ── Get offscreen percentage (for risk engine) ───────────────────────
    def get_offscreen_pct(self):
        if self.total_gaze_samples == 0:
            return 0.0
        return round(
            (self.offscreen_samples / self.total_gaze_samples) * 100, 1
        )

    # ── Helper: get iris center pixel coords ────────────────────────────
    def _get_iris_center(self, landmarks, indices, w, h):
        points = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices]
        cx     = int(np.mean([p[0] for p in points]))
        cy     = int(np.mean([p[1] for p in points]))
        return (cx, cy)

    # ── Helper: human readable message ──────────────────────────────────
    def _get_message(self, is_offscreen, gaze_locked):
        if gaze_locked and is_offscreen:
            return "Gaze locked to off-screen region — possible floating window"
        if gaze_locked:
            return "Gaze locked to fixed point"
        if is_offscreen:
            return "Looking off screen"
        return "Gaze normal"

    # ── Helper: build event dict ─────────────────────────────────────────
    def _make_event(self, event_type, **kwargs):
        return {
            "type":      event_type,
            "timestamp": time.time(),
            **kwargs,
        }

    # ── Cleanup ──────────────────────────────────────────────────────────
    def release(self):
        self.face_mesh.close()