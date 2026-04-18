# ─────────────────────────────────────────────────────
# ml_models/deepfake_detector.py
# Module 8 — Deepfake Detection
# Uses MobileNetV2 CNN to classify real vs synthetic face
# ─────────────────────────────────────────────────────

import time
import threading
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
from config import (
    DEEPFAKE_CHECK_INTERVAL_SEC,
    DEEPFAKE_CONFIDENCE_THRESHOLD,
)


class DeepfakeDetector:
    def __init__(self, event_callback, weights_path=None):
        """
        event_callback : function that receives events
        weights_path   : path to fine-tuned weights file
                         if None, uses ImageNet pretrained weights
                         as a base (good enough for testing)
        """
        self.event_callback       = event_callback
        self.weights_path         = weights_path
        self.last_check_time      = 0
        self.check_interval       = DEEPFAKE_CHECK_INTERVAL_SEC
        self.is_running           = False

        # Latest frame buffer (updated by main loop)
        self.latest_frame         = None
        self.frame_lock           = threading.Lock()

        # Detection stats
        self.total_checks         = 0
        self.synthetic_detections = 0

        # ── Build model ───────────────────────────────────────────────
        self.device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model     = self._build_model()
        self.transform = self._build_transform()

        print(f"[DeepfakeDetector] Initialized on {self.device}")

    # ── Build MobileNetV2 model ──────────────────────────────────────────
    def _build_model(self):
        """
        MobileNetV2 — lightweight CNN, fast on CPU.
        Final layer outputs 2 classes: [real, fake]
        """
        model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)

        # Replace final classifier for binary classification
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.2),
            nn.Linear(model.last_channel, 2),  # 2 classes: real / fake
        )

        # Load custom weights if provided
        if self.weights_path:
            try:
                state = torch.load(self.weights_path, map_location=self.device)
                model.load_state_dict(state)
                print(f"[DeepfakeDetector] Loaded weights from {self.weights_path}")
            except Exception as e:
                print(f"[DeepfakeDetector] Could not load weights: {e} — using pretrained")

        model.to(self.device)
        model.eval()
        return model

    # ── Image transform pipeline ─────────────────────────────────────────
    def _build_transform(self):
        return transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std =[0.229, 0.224, 0.225],
            ),
        ])

    # ── Start background detection thread ────────────────────────────────
    def start(self):
        self.is_running = True
        thread          = threading.Thread(target=self._detection_loop, daemon=True)
        thread.start()
        print("[DeepfakeDetector] Background detection started")

    # ── Stop ─────────────────────────────────────────────────────────────
    def stop(self):
        self.is_running = False
        print("[DeepfakeDetector] Stopped")

    # ── Update latest frame (called from main webcam loop) ───────────────
    def update_frame(self, frame):
        """
        Call this on every webcam frame.
        Detection runs in background every N seconds.
        """
        with self.frame_lock:
            self.latest_frame = frame.copy()

    # ── Background detection loop ─────────────────────────────────────────
    def _detection_loop(self):
        while self.is_running:
            now = time.time()
            if now - self.last_check_time >= self.check_interval:
                with self.frame_lock:
                    frame = self.latest_frame.copy() if self.latest_frame is not None else None

                if frame is not None:
                    self._run_detection(frame)
                    self.last_check_time = now

            time.sleep(1.0)

    # ── Run detection on a single frame ──────────────────────────────────
    def _run_detection(self, frame):
        try:
            # ── Crop face region ──────────────────────────────────────
            face_crop = self._crop_face(frame)
            if face_crop is None:
                return   # no face found — skip

            # ── Preprocess ────────────────────────────────────────────
            rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            tensor   = self.transform(rgb_crop).unsqueeze(0).to(self.device)

            # ── Inference ─────────────────────────────────────────────
            with torch.no_grad():
                logits      = self.model(tensor)
                probs       = torch.softmax(logits, dim=1).squeeze()
                real_prob   = float(probs[0])
                fake_prob   = float(probs[1])

            is_synthetic = fake_prob > DEEPFAKE_CONFIDENCE_THRESHOLD
            confidence   = round(fake_prob if is_synthetic else real_prob, 3)

            self.total_checks += 1
            if is_synthetic:
                self.synthetic_detections += 1

            self._send_event({
                "type":         "deepfake",
                "is_synthetic": is_synthetic,
                "real_prob":    round(real_prob, 3),
                "fake_prob":    round(fake_prob, 3),
                "confidence":   confidence,
                "flagged":      is_synthetic,
                "message":      (
                    f"Synthetic face detected — {fake_prob:.1%} confidence"
                    if is_synthetic else
                    f"Real face confirmed — {real_prob:.1%} confidence"
                ),
                "timestamp":    time.time(),
            })

        except Exception as e:
            print(f"[DeepfakeDetector] Detection error: {e}")

    # ── Crop face from frame using OpenCV ────────────────────────────────
    def _crop_face(self, frame):
        """
        Uses OpenCV Haar cascade to find and crop face.
        Falls back to center crop if no face detected.
        """
        gray     = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            # Fall back to center crop
            h, w   = frame.shape[:2]
            margin = min(h, w) // 4
            return frame[margin:h-margin, margin:w-margin]

        # Crop largest face
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        padding       = 20
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + fw + padding)
        y2 = min(frame.shape[0], y + fh + padding)
        return frame[y1:y2, x1:x2]

    # ── Get stats ────────────────────────────────────────────────────────
    def get_stats(self):
        return {
            "total_checks":         self.total_checks,
            "synthetic_detections": self.synthetic_detections,
            "detection_rate":       round(
                self.synthetic_detections / self.total_checks, 3
            ) if self.total_checks > 0 else 0,
        }

    # ── Send event via callback ──────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[DeepfakeDetector] Callback error: {e}")