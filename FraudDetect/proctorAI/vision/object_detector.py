# ─────────────────────────────────────────────────────
# vision/object_detector.py
# Module 11 — Physical Object Detection
# Uses YOLOv8-nano to detect banned items held by the
# candidate: phones, books, paper, second laptops, etc.
#
# YOLOv8-nano is pre-trained on COCO (80 classes).
# Relevant COCO classes we flag:
#   67 = cell phone
#   73 = book
#   63 = laptop  (second device)
#   84 = book / notebook (same as 73 in some builds)
# ─────────────────────────────────────────────────────

import time
import threading
import cv2
from config import (
    OBJECT_DETECT_INTERVAL_FRAMES,
    OBJECT_CONFIDENCE_THRESHOLD,
    BANNED_OBJECT_CLASSES,
)


class ObjectDetector:
    """
    Runs YOLOv8-nano on every Nth frame.
    Fires a flagged event whenever a banned object is detected.

    Usage
    -----
    detector = ObjectDetector(event_callback=on_event)
    detector.start()                # loads model in background thread

    # in the main webcam loop:
    events = detector.process_frame(frame)
    frame  = detector.draw_debug(frame)
    """

    # Human-readable names for the COCO class IDs we care about
    CLASS_NAMES = {
    67: "cell phone",
    73: "book",
    63: "laptop",
    76: "scissors",
    84: "book",
    66: "keyboard",
    77: "remote",
}

    def __init__(self, event_callback):
        self.event_callback = event_callback

        # Frame counter — we only run inference every N frames
        self._frame_count   = 0
        self._model         = None          # loaded lazily in start()
        self._model_ready   = False
        self._model_error   = None

        # Last detections — kept for draw_debug between inference runs
        self._last_detections = []          # list of dicts: {label, conf, box}
        self._last_check_time = 0.0

        # Stats
        self.total_detections = 0
        self.flagged_count    = 0

    # ── Start: load YOLOv8-nano in a background thread ──────────────────
    def start(self):
        """
        Loads the YOLOv8-nano weights in a daemon thread so startup is
        non-blocking.  The model downloads automatically on first run
        (~6 MB) and is cached in ~/.cache/ultralytics.
        """
        t = threading.Thread(target=self._load_model, daemon=True)
        t.start()
        print("[ObjectDetector] Loading YOLOv8-nano weights (background)...")

    def _load_model(self):
        try:
            from ultralytics import YOLO  # type: ignore[import-untyped]
            self._model       = YOLO("yolov8n.pt")   # nano — fastest
            self._model_ready = True
            print("[ObjectDetector] YOLOv8-nano ready")
        except Exception as e:
            self._model_error = str(e)
            print(f"[ObjectDetector] Failed to load model: {e}")

    # ── Stop ─────────────────────────────────────────────────────────────
    def stop(self):
        self._model       = None
        self._model_ready = False
        print("[ObjectDetector] Stopped")

    # ── Per-frame call ────────────────────────────────────────────────────
    def process_frame(self, frame):
        """
        Call on every webcam frame.  Actually runs YOLO only every
        OBJECT_DETECT_INTERVAL_FRAMES frames; returns [] on skipped frames.
        Returns a list of events (may be empty).
        """
        events = []
        self._frame_count += 1

        # Skip if model not loaded yet or not enough frames elapsed
        if not self._model_ready:
            return events
        if self._frame_count % OBJECT_DETECT_INTERVAL_FRAMES != 0:
            return events

        try:
            detections = self._run_inference(frame)
        except Exception as e:
            print(f"[ObjectDetector] Inference error: {e}")
            return events

        self._last_detections = detections
        self._last_check_time = time.time()

        for det in detections:
            self.total_detections += 1
            flagged = det["label"] in BANNED_OBJECT_CLASSES
            if flagged:
                self.flagged_count += 1

            event = {
                "type":       "banned_object",
                "label":      det["label"],
                "confidence": round(det["conf"], 3),
                "box":        det["box"],  # (x1, y1, x2, y2) pixels
                "flagged":    flagged,
                "message": (
                    f"Banned object detected: {det['label']} "
                    f"({det['conf']*100:.0f}% conf)"
                    if flagged else
                    f"Object detected: {det['label']}"
                ),
                "timestamp":  time.time(),
            }
            events.append(event)

            # Fire immediately via callback for flagged items
            if flagged:
                try:
                    self.event_callback(event)
                except Exception as cb_err:
                    print(f"[ObjectDetector] Callback error: {cb_err}")

        return events

    # ── Run YOLOv8 inference ──────────────────────────────────────────────
    def _run_inference(self, frame):
        """
        Returns list of dicts: {label, conf, box} for every detection
        above OBJECT_CONFIDENCE_THRESHOLD.
        We run on a half-resolution copy for speed (320×240).
        """
        small = cv2.resize(frame, (320, 240))
        sx    = frame.shape[1] / 320
        sy    = frame.shape[0] / 240

        results = self._model(
            small,
            verbose  = False,
            conf     = OBJECT_CONFIDENCE_THRESHOLD,
            classes  = list(self.CLASS_NAMES.keys()),
        )

        detections = []
        for r in results:
            for box in r.boxes:
                cid   = int(box.cls[0])
                conf  = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                # Scale back to original frame coordinates
                detections.append({
                    "label": self.CLASS_NAMES.get(cid, f"class_{cid}"),
                    "conf":  conf,
                    "box":   (
                        int(x1 * sx), int(y1 * sy),
                        int(x2 * sx), int(y2 * sy),
                    ),
                })
        return detections

    # ── Draw debug overlay ────────────────────────────────────────────────
    def draw_debug(self, frame):
        """
        Draws bounding boxes for the most recently detected objects.
        Call this inside the main loop (uses cached last_detections,
        so it is free on frames where inference was skipped).
        """
        for det in self._last_detections:
            x1, y1, x2, y2 = det["box"]
            label = det["label"]
            conf  = det["conf"]
            flagged = label in BANNED_OBJECT_CLASSES

            color = (50, 50, 220) if flagged else (180, 180, 60)   # red / yellow
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            tag = f"{label} {conf*100:.0f}%"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
            cv2.putText(
                frame, tag,
                (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (255, 255, 255), 1, cv2.LINE_AA,
            )
        return frame

    # ── Stats ──────────────────────────────────────────────────────────────
    def get_stats(self):
        return {
            "model_ready":      self._model_ready,
            "total_detections": self.total_detections,
            "flagged_count":    self.flagged_count,
            "last_detections":  [
                {"label": d["label"], "conf": round(d["conf"], 2)}
                for d in self._last_detections
            ],
        }
