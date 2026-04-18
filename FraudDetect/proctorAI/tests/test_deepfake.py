# ─────────────────────────────────────────────────────
# tests/test_deepfake.py
# Run from inside proctorAI/:
# python tests/test_deepfake.py
# Press Q to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import time
from ml_models.deepfake_detector import DeepfakeDetector


def on_event(event):
    status = "FLAGGED" if event["flagged"] else "ok"
    print(
        f"  [{status}] "
        f"real={event['real_prob']} "
        f"fake={event['fake_prob']} "
        f"| {event['message']}"
    )


def main():
    cap      = cv2.VideoCapture(0)
    detector = DeepfakeDetector(event_callback=on_event)

    print("\n── Deepfake Detection Test ────────────────")
    print("  Detection runs every 60s in background")
    print("  For testing, interval is reduced to 5s")
    print("  Press Q in video window to quit\n")

    # Reduce interval for testing
    detector.check_interval = 5

    detector.start()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Cannot access webcam.")
            break

        # Feed frames to detector
        detector.update_frame(frame)

        # Show frame
        cv2.putText(
            frame,
            f"Checks: {detector.total_checks} | Synthetic: {detector.synthetic_detections}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )
        cv2.imshow("Deepfake Detection Test — press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    detector.stop()
    cap.release()
    cv2.destroyAllWindows()

    stats = detector.get_stats()
    print(f"\n── Session Stats ───────────────────────────")
    print(f"  Total checks        : {stats['total_checks']}")
    print(f"  Synthetic detections: {stats['synthetic_detections']}")
    print(f"── Test complete ───────────────────────────\n")


if __name__ == "__main__":
    main()