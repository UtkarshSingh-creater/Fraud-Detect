# ─────────────────────────────────────────────────────
# tests/test_head_pose.py
# Run from inside proctorAI/:
# python tests/test_head_pose.py
# Press Q to quit
# ─────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
from vision.head_pose import HeadPoseEstimator

def main():
    cap       = cv2.VideoCapture(0)
    estimator = HeadPoseEstimator()

    print("\n── Head Pose Test ─────────────────────────")
    print("  Move your head left/right/up/down")
    print("  FLAGGED will print when threshold exceeded")
    print("  Press Q in video window to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Cannot access webcam.")
            break

        events = estimator.process_frame(frame)
        for e in events:
            if e["flagged"]:
                print(f"  [FLAGGED] yaw={e['yaw']} pitch={e['pitch']} | {e['message']}")

        frame = estimator.draw_debug(frame)
        cv2.imshow("Head Pose Test — press Q to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    estimator.release()
    cap.release()
    cv2.destroyAllWindows()
    print("\n── Test complete ──────────────────────────\n")

if __name__ == "__main__":
    main()