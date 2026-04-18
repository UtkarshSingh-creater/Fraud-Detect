# ─────────────────────────────────────────────────────
# vision/face_detector.py
# Module 1 & 2 — Face Detection, Recognition, Multiple Face Detection
# ─────────────────────────────────────────────────────

import cv2
import face_recognition
import numpy as np
import time
from FraudDetect.proctorAI.config import (
    FACE_MISSING_ALERT_SECONDS,
    FACE_VERIFY_EVERY_N_FRAMES,
    FACE_MATCH_TOLERANCE,
    MAX_ALLOWED_FACES,
)


class FaceDetector:
    def __init__(self):
        self.baseline_encoding   = None   # face encoding captured at session start
        self.frame_count         = 0
        self.last_face_seen_time = time.time()
        self.alerts              = []     # list of events to send to backend

    # ── Step 1: Capture baseline face at session start ──────────────────
    def capture_baseline(self, frame):
        """
        Call this once at the start of the interview.
        Encodes the candidate's face as the reference.
        Returns True if baseline was captured, False if no face found.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)

        if len(encodings) == 0:
            print("[FaceDetector] No face found for baseline. Retrying...")
            return False

        self.baseline_encoding = encodings[0]
        print("[FaceDetector] Baseline face captured successfully.")
        return True

    # ── Step 2: Process every frame ─────────────────────────────────────
    def process_frame(self, frame):
        """
        Call this on every frame from the webcam.
        Returns a list of events to send to the backend.
        """
        self.frame_count += 1
        events = []
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect all face locations in frame
        face_locations = face_recognition.face_locations(rgb)
        face_count     = len(face_locations)

        # ── Check 1: No face detected ────────────────────────────────
        if face_count == 0:
            elapsed = time.time() - self.last_face_seen_time
            if elapsed >= FACE_MISSING_ALERT_SECONDS:
                events.append(self._make_event(
                    "face_missing",
                    flagged  = True,
                    message  = f"No face detected for {round(elapsed, 1)}s",
                    duration = round(elapsed, 1),
                ))
        else:
            self.last_face_seen_time = time.time()

        # ── Check 2: Multiple faces detected ─────────────────────────
        if face_count > MAX_ALLOWED_FACES:
            events.append(self._make_event(
                "multiple_faces",
                flagged     = True,
                face_count  = face_count,
                message     = f"{face_count} faces detected in frame",
            ))

        # ── Check 3: Verify same person (every N frames) ─────────────
        if (
            face_count > 0
            and self.baseline_encoding is not None
            and self.frame_count % FACE_VERIFY_EVERY_N_FRAMES == 0
        ):
            encodings = face_recognition.face_encodings(rgb, face_locations)
            if encodings:
                match    = face_recognition.compare_faces(
                    [self.baseline_encoding],
                    encodings[0],
                    tolerance = FACE_MATCH_TOLERANCE,
                )
                distance = face_recognition.face_distance(
                    [self.baseline_encoding],
                    encodings[0],
                )[0]
                same_person = bool(match[0])
                confidence  = round(1 - float(distance), 2)

                events.append(self._make_event(
                    "face_verify",
                    flagged     = not same_person,
                    same_person = same_person,
                    confidence  = confidence,
                    message     = "Same person" if same_person else "Different person detected!",
                ))

        return events

    # ── Helper: Draw boxes on frame (for debugging) ──────────────────────
    def draw_debug(self, frame):
        """
        Draws face boxes on frame so you can visually debug.
        Only use during development — disable in production.
        """
        rgb            = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb)

        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(
                frame, "Face",
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 255, 0), 2,
            )
        return frame

    # ── Helper: Build a clean event dict ────────────────────────────────
    def _make_event(self, event_type, **kwargs):
        return {
            "type":      event_type,
            "timestamp": time.time(),
            **kwargs,
        }