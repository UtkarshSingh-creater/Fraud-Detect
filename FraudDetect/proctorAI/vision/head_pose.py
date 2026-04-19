# ─────────────────────────────────────────────────────
# vision/head_pose.py
# Module 4 — Head Pose Estimation
# Detects abnormal head movements (yaw, pitch, roll)
# ─────────────────────────────────────────────────────

import cv2
import numpy as np
import mediapipe as mp
import time
from config import (
    HEAD_YAW_THRESHOLD,
    HEAD_PITCH_THRESHOLD,
    HEAD_POSE_ALERT_COUNT,
)


class HeadPoseEstimator:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces            = 1,
            refine_landmarks         = True,
            min_detection_confidence = 0.5,
            min_tracking_confidence  = 0.5,
        )

        # 3D model points of a generic face
        self.model_points = np.array([
            (0.0,    0.0,    0.0),     # Nose tip
            (0.0,   -330.0, -65.0),    # Chin
            (-225.0, 170.0, -135.0),   # Left eye corner
            (225.0,  170.0, -135.0),   # Right eye corner
            (-150.0,-150.0, -125.0),   # Left mouth corner
            (150.0, -150.0, -125.0),   # Right mouth corner
        ], dtype=np.float64)

        # MediaPipe landmark indices for the 6 points above
        self.LANDMARK_IDS = [1, 152, 263, 33, 287, 57]

        # Consecutive violation counter
        self.violation_count = 0
        self.last_yaw        = 0.0
        self.last_pitch      = 0.0
        self.last_roll       = 0.0

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

        # ── Get 2D image points ──────────────────────────────────────
        image_points = np.array([
            (landmarks[i].x * w, landmarks[i].y * h)
            for i in self.LANDMARK_IDS
        ], dtype=np.float64)

        # ── Camera internals (approximate) ──────────────────────────
        focal_length    = w
        center          = (w / 2, h / 2)
        camera_matrix   = np.array([
            [focal_length, 0,            center[0]],
            [0,            focal_length, center[1]],
            [0,            0,            1         ],
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        # ── Solve PnP — get rotation vector ─────────────────────────
        success, rotation_vec, translation_vec = cv2.solvePnP(
            self.model_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags = cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return events

        # ── Convert rotation vector to Euler angles ──────────────────
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        pose_mat        = cv2.hconcat([rotation_mat, translation_vec])  # 3×4
        # ── Convert rotation vector to Euler angles ──────────────────
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)

        # Build proper 4x4 projection matrix
        proj_matrix = np.hstack([rotation_mat, translation_vec])
        proj_matrix = np.vstack([proj_matrix, [0, 0, 0, 1]])

        # Decompose to get euler angles
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(
            proj_matrix[:3, :]
        )

        pitch = float(euler_angles[0])
        yaw   = float(euler_angles[1])
        roll  = float(euler_angles[2])

        # Normalize angles to -180 to 180 range
        pitch = pitch % 360
        yaw   = yaw   % 360
        roll  = roll  % 360

        if pitch > 180: pitch -= 360
        if yaw   > 180: yaw   -= 360
        if roll  > 180: roll  -= 360

        pitch = float(euler_angles[0])
        yaw   = float(euler_angles[1])
        roll  = float(euler_angles[2])

        self.last_yaw   = round(yaw,   2)
        self.last_pitch = round(pitch, 2)
        self.last_roll  = round(roll,  2)

        # ── Check thresholds ─────────────────────────────────────────
        yaw_flagged   = abs(yaw)   > HEAD_YAW_THRESHOLD
        pitch_flagged = abs(pitch) > HEAD_PITCH_THRESHOLD
        flagged       = yaw_flagged or pitch_flagged

        if flagged:
            self.violation_count += 1
        else:
            # Reset immediately so should_alert goes False on the very next
            # normal frame — prevents "ghost flagging" when count drains slowly.
            self.violation_count = 0

        # Only alert after N consecutive violations
        should_alert = self.violation_count >= HEAD_POSE_ALERT_COUNT

        events.append(self._make_event(
            "head_pose",
            yaw             = self.last_yaw,
            pitch           = self.last_pitch,
            roll            = self.last_roll,
            flagged         = should_alert,
            yaw_flagged     = yaw_flagged,
            pitch_flagged   = pitch_flagged,
            violation_count = self.violation_count,
            message         = self._get_message(yaw_flagged, pitch_flagged, should_alert),
        ))

        return events

    # ── Draw debug overlay on frame ──────────────────────────────────────
    def draw_debug(self, frame):
        """
        Draws yaw/pitch/roll values on frame.
        Only use during development.
        """
        cv2.putText(frame, f"Yaw:   {self.last_yaw:.1f} deg",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Pitch: {self.last_pitch:.1f} deg",
            (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Roll:  {self.last_roll:.1f} deg",
            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        color = (0, 0, 255) if self.violation_count >= HEAD_POSE_ALERT_COUNT else (0, 255, 0)
        cv2.putText(frame, f"Violations: {self.violation_count}",
            (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return frame

    # ── Helper: human readable message ──────────────────────────────────
    def _get_message(self, yaw_flagged, pitch_flagged, should_alert):
        if not should_alert:
            return "Head pose normal"
        if yaw_flagged and pitch_flagged:
            return "Head turned and tilted — suspicious movement"
        if yaw_flagged:
            return "Head turned too far left/right"
        if pitch_flagged:
            return "Head tilted too far up/down"
        return "Head pose normal"

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