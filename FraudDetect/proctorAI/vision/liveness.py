# ─────────────────────────────────────────────────────
# vision/liveness.py
# Module 5 — Liveness Detection
# Blink detection + head movement to confirm live person
# ─────────────────────────────────────────────────────

import cv2
import mediapipe as mp
import numpy as np
import time
from config import (
    BLINK_EAR_THRESHOLD,
    BLINK_CONSEC_FRAMES,
    MIN_BLINK_RATE_PER_MINUTE,
    MAX_BLINK_RATE_PER_MINUTE,
)


class LivenessDetector:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces            = 1,
            refine_landmarks         = True,
            min_detection_confidence = 0.5,
            min_tracking_confidence  = 0.5,
        )

        # MediaPipe indices for left and right eye
        # Each list has 6 points forming the eye shape
        self.LEFT_EYE  = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33,  160, 158, 133, 153, 144]

        # Blink tracking
        self.blink_count        = 0
        self.consec_frame_count = 0   # frames eye has been closed
        self.eye_closed         = False

        # Session timing
        self.session_start      = time.time()
        self.last_event_time    = time.time()

        # Head movement tracking (for liveness)
        self.prev_nose_x        = None
        self.prev_nose_y        = None
        self.movement_samples   = []

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
            return events

        landmarks = result.multi_face_landmarks[0].landmark

        # ── Calculate EAR for both eyes ──────────────────────────────
        left_ear  = self._eye_aspect_ratio(landmarks, self.LEFT_EYE,  w, h)
        right_ear = self._eye_aspect_ratio(landmarks, self.RIGHT_EYE, w, h)
        avg_ear   = (left_ear + right_ear) / 2.0

        # ── Blink detection ──────────────────────────────────────────
        if avg_ear < BLINK_EAR_THRESHOLD:
            self.consec_frame_count += 1
            self.eye_closed          = True
        else:
            # Eye just reopened after being closed
            if self.eye_closed and self.consec_frame_count >= BLINK_CONSEC_FRAMES:
                self.blink_count += 1
            self.consec_frame_count = 0
            self.eye_closed         = False

        # ── Head micro-movement tracking ─────────────────────────────
        nose_x = landmarks[1].x
        nose_y = landmarks[1].y

        if self.prev_nose_x is not None:
            movement = np.sqrt(
                (nose_x - self.prev_nose_x) ** 2 +
                (nose_y - self.prev_nose_y) ** 2
            )
            self.movement_samples.append(movement)
            # Keep only last 100 samples
            if len(self.movement_samples) > 100:
                self.movement_samples.pop(0)

        self.prev_nose_x = nose_x
        self.prev_nose_y = nose_y

        # ── Calculate blink rate per minute ──────────────────────────
        elapsed_minutes = (time.time() - self.session_start) / 60.0
        blink_rate      = (
            self.blink_count / elapsed_minutes
            if elapsed_minutes > 0.1 else 0
        )

        # ── Determine liveness ───────────────────────────────────────
        avg_movement  = np.mean(self.movement_samples) if self.movement_samples else 0
        has_movement  = avg_movement > 0.0001   # some natural micro-movement
        blink_rate_ok = (
            MIN_BLINK_RATE_PER_MINUTE <= blink_rate <= MAX_BLINK_RATE_PER_MINUTE
            if elapsed_minutes > 0.5 else True  # skip check in first 30 seconds
        )
        is_live = has_movement and blink_rate_ok

        # ── Flag conditions ──────────────────────────────────────────
        no_blink_flag    = blink_rate < MIN_BLINK_RATE_PER_MINUTE and elapsed_minutes > 0.5
        too_still_flag   = not has_movement and len(self.movement_samples) >= 50
        flagged          = no_blink_flag or too_still_flag

        # ── Send event every 2 seconds ───────────────────────────────
        now = time.time()
        if now - self.last_event_time >= 2.0:
            self.last_event_time = now
            events.append(self._make_event(
                "liveness",
                is_live        = is_live,
                flagged        = flagged,
                blink_count    = self.blink_count,
                blink_rate     = round(blink_rate, 1),
                avg_ear        = round(avg_ear, 3),
                avg_movement   = round(float(avg_movement), 6),
                no_blink_flag  = no_blink_flag,
                too_still_flag = too_still_flag,
                message        = self._get_message(is_live, no_blink_flag, too_still_flag),
            ))

        return events

    # ── Draw debug overlay ───────────────────────────────────────────────
    def draw_debug(self, frame):
        """
        Draws blink count and EAR value on frame.
        Only use during development.
        """
        h, w   = frame.shape[:2]
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.face_mesh.process(rgb)

        if result.multi_face_landmarks:
            landmarks = result.multi_face_landmarks[0].landmark
            left_ear  = self._eye_aspect_ratio(landmarks, self.LEFT_EYE,  w, h)
            right_ear = self._eye_aspect_ratio(landmarks, self.RIGHT_EYE, w, h)
            avg_ear   = (left_ear + right_ear) / 2.0

            color = (0, 0, 255) if avg_ear < BLINK_EAR_THRESHOLD else (0, 255, 0)

            cv2.putText(frame, f"EAR: {avg_ear:.3f}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.putText(frame, f"Blinks: {self.blink_count}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            elapsed_minutes = (time.time() - self.session_start) / 60.0
            blink_rate = self.blink_count / elapsed_minutes if elapsed_minutes > 0.1 else 0
            cv2.putText(frame, f"Blink rate: {blink_rate:.1f}/min",
                (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            status = "LIVE" if self.movement_samples and np.mean(self.movement_samples) > 0.0001 else "STILL"
            cv2.putText(frame, f"Status: {status}",
                (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        return frame

    # ── Helper: Eye Aspect Ratio ─────────────────────────────────────────
    def _eye_aspect_ratio(self, landmarks, eye_indices, w, h):
        """
        EAR = ratio of eye height to eye width.
        Low EAR = eye closed (blink).
        """
        points = [
            (int(landmarks[i].x * w), int(landmarks[i].y * h))
            for i in eye_indices
        ]

        # Vertical distances
        v1 = np.linalg.norm(np.array(points[1]) - np.array(points[5]))
        v2 = np.linalg.norm(np.array(points[2]) - np.array(points[4]))

        # Horizontal distance
        h1 = np.linalg.norm(np.array(points[0]) - np.array(points[3]))

        ear = (v1 + v2) / (2.0 * h1) if h1 > 0 else 0.0
        return ear

    # ── Helper: human readable message ──────────────────────────────────
    def _get_message(self, is_live, no_blink_flag, too_still_flag):
        if too_still_flag and no_blink_flag:
            return "No movement and no blinks — possible photo/video attack"
        if too_still_flag:
            return "Face too still — possible static image"
        if no_blink_flag:
            return "No blinks detected — possible non-live face"
        return "Liveness confirmed"

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