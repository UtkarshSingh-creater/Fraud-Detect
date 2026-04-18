# ─────────────────────────────────────────────────────
# tests/test_object_detector.py
# Run from inside proctorAI/:
# python tests/test_object_detector.py
# Press Q to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from vision.object_detector import ObjectDetector


def on_event(event):
    print(f"  [FLAGGED] {event['label']} detected — {event['confidence']:.0%} confidence")


def main():
    cap      = cv2.VideoCapture(0)
    detector = ObjectDetector(event_callback=on_event)

    print("\n── Object Detector Test ───────────────────")
    print("  Hold a phone/book in front of camera")
    print("  Banned objects will be flagged")
    print("  Press Q to quit\n")
    print("  Waiting for YOLOv8-nano model to load...\n")

    detector.start()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detector.process_frame(frame)

        # Draw detections — use draw_debug which has the full box + flagged logic
        detector.draw_debug(frame)

        # Print stats line
        stats = detector.get_stats()
        flagged_now = [d for d in stats["last_detections"] if d["label"] in detector.CLASS_NAMES.values()]
        _ = flagged_now   # available for debugging

        status = "READY" if detector._model_ready else "Loading..."
        cv2.putText(frame, f"YOLO: {status}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("Object Detector Test — press Q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    detector.stop()
    cap.release()
    cv2.destroyAllWindows()
    print("\n── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()