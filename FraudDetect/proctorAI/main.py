# ─────────────────────────────────────────────────────
# main.py — ProctorAI Entry Point
# Wires all 10 modules into one running system
#
# Run from inside proctorAI/:
#   python main.py
# ─────────────────────────────────────────────────────

import cv2
import time
import signal
import sys
import threading
import ctypes

from vision.face_detector        import FaceDetector
from vision.gaze_tracker         import GazeTracker
from vision.head_pose            import HeadPoseEstimator
from vision.liveness             import LivenessDetector
from vision.object_detector      import ObjectDetector
from biometrics.keystroke        import KeystrokeMonitor
from biometrics.mouse            import MouseMonitor
from audio.audio_monitor         import AudioMonitor
from ml_models.deepfake_detector import DeepfakeDetector
from ml_models.temporal_analyzer import TemporalAnalyzer
from scoring.risk_engine         import RiskEngine
from biometrics.window_monitor   import WindowMonitor
from config import (
    CAMERA_INDEX,
    FRAME_WIDTH,
    FRAME_HEIGHT,
    FPS,
    BANNED_PROCESSES,
    SESSION_ID,
)

# ── Debug overlay toggle (set False to run headless / in production) ──────
DEBUG_OVERLAY = True

# ── Per-module enable flags ───────────────────────────────────────────────
# All three pynput/PyAudio modules need macOS permissions before enabling.
# WITHOUT the permission, pynput/PyAudio sends SIGTRAP -> immediate crash.
#
# KEYSTROKE + MOUSE: System Settings > Privacy & Security > Input Monitoring
#                   -> click + -> add Terminal.app
# AUDIO:             System Settings > Privacy & Security > Microphone
#                   -> click + -> add Terminal.app
#
# After granting, quit+reopen Terminal, then set the flag to True.
ENABLE_KEYSTROKE = True
ENABLE_MOUSE     = True
ENABLE_AUDIO     = True


# ─────────────────────────────────────────────────────────────────────────
# macOS Accessibility Pre-flight Check
# ─────────────────────────────────────────────────────────────────────────
def check_accessibility():
    """
    Returns True if the Terminal has Accessibility (input monitoring) access.
    Without this, pynput's mouse/keyboard listeners send SIGTRAP → crash.
    """
    try:
        app_svc = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/"
            "ApplicationServices"
        )
        return bool(app_svc.CGPreflightListenEventAccess())
    except Exception:
        return True   # can't check — assume OK and let it fail gracefully


def require_accessibility():
    """
    Checks accessibility and prints a fix guide if not granted.
    Does NOT exit — pynput modules get safely skipped instead.
    """
    if not check_accessibility():
        print()
        print("  ┌─────────────────────────────────────────────────────────┐")
        print("  │  ⚠️  ACCESSIBILITY PERMISSION REQUIRED                   │")
        print("  │                                                         │")
        print("  │  Keystroke and mouse monitoring need Accessibility       │")
        print("  │  access. Without it, pynput crashes the process.        │")
        print("  │                                                         │")
        print("  │  Fix:                                                   │")
        print("  │  1. Open System Settings                                │")
        print("  │  2. Privacy & Security → Accessibility                  │")
        print("  │  3. Add your Terminal app (Terminal.app or iTerm2)      │")
        print("  │  4. Re-run: python main.py                              │")
        print("  └─────────────────────────────────────────────────────────┘")
        print()
        print("  [main] Continuing without keystroke/mouse monitoring...\n")
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────
# SIGTRAP handler - thread-safe, fires only once
# Cannot use print() in signal handlers: a background thread may hold
# stdout's lock causing "reentrant BufferedWriter" -> second crash.
# Instead: os.write(fd, bytes) - async-signal-safe at the fd level.
# os._exit(1) - hard exit that skips all Python cleanup / __del__ / atexit.
# _exiting flag - prevents multiple threads from re-entering before _exit.
# ──────────────────────────────────────────────────────────────────────────
import os as _os
import ctypes as _ctypes
_exiting = _ctypes.c_int(0)   # atomic flag: 0 = not exiting, 1 = exiting

def _handle_sigtrap(signum, frame):
    # Atomically check-and-set: only the FIRST thread that gets here runs
    if _ctypes.atomic_add(_exiting, 1) if hasattr(_ctypes, 'atomic_add') \
       else _exiting.value:   # fallback: check flag (good enough for signal context)
        return
    _exiting.value = 1
    msg = (
        b"\n"
        b"  [SIGTRAP] A module crashed (hardware trap).\n"
        b"  On macOS, pynput keyboard/mouse requires Input Monitoring permission\n"
        b"  and PyAudio requires Microphone permission.\n"
        b"\n"
        b"  Step 1: System Settings > Privacy & Security > Input Monitoring\n"
        b"          Click + and add Terminal.app\n"
        b"          Then set ENABLE_KEYSTROKE = True and ENABLE_MOUSE = True\n"
        b"\n"
        b"  Step 2: System Settings > Privacy & Security > Microphone\n"
        b"          Click + and add Terminal.app\n"
        b"          Then set ENABLE_AUDIO = True\n"
        b"\n"
        b"  Step 3: Quit Terminal completely, reopen it, and run python main.py\n"
        b"\n"
    )
    _os.write(2, msg)
    _os._exit(1)

try:
    signal.signal(signal.SIGTRAP, _handle_sigtrap)
except (OSError, ValueError):
    pass


# ─────────────────────────────────────────────────────────────────────────
# Safe module start — wraps .start() so one failure skips, not crashes.
# For pynput modules: also waits 300 ms and checks .listener.is_alive()
# to detect a silent SIGTRAP before it kills the whole process.
# ─────────────────────────────────────────────────────────────────────────
def safe_start(module, name, liveness_check=False):
    """
    Calls module.start(). If it raises, prints a warning and continues.
    When liveness_check=True (pynput modules): waits 300 ms after start
    and verifies the listener thread is still alive.  If not, prints a
    clear permission error and skips the module instead of crashing.
    Returns True on success, False on failure.
    """
    try:
        module.start()
    except Exception as e:
        print(f"  [main] ⚠️  {name} failed to start: {e} — skipping")
        return False

    if liveness_check:
        # pynput modules expose .listener; AudioMonitor exposes .thread
        bg_thread = getattr(module, "listener", None) or getattr(module, "thread", None)
        if bg_thread is not None:
            time.sleep(0.35)   # give the native thread time to crash if permissions are wrong
            if not bg_thread.is_alive():
                print(
                    f"\n  [main] ⚠️  {name} background thread died immediately after start."
                    f"\n         This almost always means macOS has not yet applied the"
                    f"\n         Input Monitoring or Microphone permission to this Terminal."
                    f"\n"
                    f"\n         Fix: Cmd+Q Terminal completely → reopen → re-run python main.py"
                    f"\n         (Permission grants require a full Terminal restart to take effect)"
                    f"\n"
                )
                return False

    return True

# ── How often to scan for banned processes (seconds) ─────────────────────
PROCESS_CHECK_INTERVAL = 10


# ─────────────────────────────────────────────────────────────────────────
# Module 11 (lightweight) — Banned Process Monitor
# ─────────────────────────────────────────────────────────────────────────
def start_process_monitor(on_event):
    """
    Background thread that scans running processes every N seconds.
    Fires a flagged event if a banned app (from config.py) is found.
    Requires: pip install psutil
    """
    def _loop():
        while True:
            try:
                import psutil
                running_names = [
                    p.info["name"].lower()
                    for p in psutil.process_iter(["name"])
                    if p.info["name"]
                ]
                for proc_name in running_names:
                    for banned in BANNED_PROCESSES:
                        if banned.lower() in proc_name:
                            on_event({
                                "type":         "process",
                                "flagged":      True,
                                "process_name": proc_name,
                                "message":      f"Banned application running: {proc_name}",
                                "timestamp":    time.time(),
                            })
                            break
            except ImportError:
                # psutil not installed — silently skip process monitoring
                return
            except Exception as e:
                print(f"[ProcessMonitor] Error: {e}")

            time.sleep(PROCESS_CHECK_INTERVAL)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print("[ProcessMonitor] Started — scanning for banned processes")


# ─────────────────────────────────────────────────────────────────────────
# Central Event Callback
# Every event from every module passes through here — single funnel.
# ─────────────────────────────────────────────────────────────────────────
def make_on_event(risk_engine, temporal_analyzer):
    """
    Returns the on_event() callback used by all modules.

    Flow:
        module fires event
            → temporal_analyzer.add_event()  (builds LSTM context)
            → risk_engine.process_event()    (recomputes risk score)
            → print / send to backend if flagged
    """
    def on_event(event):
        # 1. Feed into temporal LSTM context window
        temporal_analyzer.add_event(event)

        # 2. Feed into risk engine — get updated risk score
        risk_output = risk_engine.process_event(event)

        # 3. Print flagged events to console
        #    ── Replace this block with ws_client.send(risk_output) ──
        if event.get("flagged"):
            level = risk_output["risk_level"]
            score = risk_output["risk_score"]
            conf  = risk_output["confidence"]
            msg   = event.get("message", "")
            etype = event.get("type", "unknown")
            print(
                f"  [{level}] score={score} conf={conf} "
                f"| {etype} — {msg}"
            )

    return on_event


# ─────────────────────────────────────────────────────────────────────────
# Baseline Face Capture
# ─────────────────────────────────────────────────────────────────────────
def capture_baseline(cap, face_detector):
    """
    Loops until a face is found and encoded as the session baseline.
    Console-only (no cv2.imshow/waitKey) — avoids the macOS/Apple Silicon
    SIGTRAP that cv2.waitKey() raises when called before pynput has started.
    Returns True on success, False on timeout.
    """
    print("\n[main] ── Baseline Capture ─────────────────────────────")
    print("[main]   Look directly at the camera.")
    print("[main]   Waiting for face detection...")

    max_wait_s  = 30          # give up after 30 seconds
    deadline    = time.time() + max_wait_s
    dot_timer   = time.time()

    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        # Try to capture the baseline face
        if face_detector.capture_baseline(frame):
            print("\n[main]   ✓ Baseline face captured — session starting\n")
            return True

        # Print a dot every second so the user knows we're alive
        if time.time() - dot_timer >= 1.0:
            print(".", end="", flush=True)
            dot_timer = time.time()

        time.sleep(0.05)   # ~20 fps poll, no GUI calls

    print("\n[main]   ✗ Baseline capture timed out after 30s — exiting")
    return False


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# Unified HUD renderer  (ASCII-only — OpenCV does not support Unicode text)
# Layout:
#   Left sidebar 200px : Head Pose / Gaze / Liveness / Signals
#   Top-right badge    : risk score (3-line, no overlap)
#   Bottom bar         : session / frame / events / confidence
#   Video layer        : face box + iris dots only
# ─────────────────────────────────────────────────────────────────────────
def _draw_hud(frame, frame_count, risk_engine,
              gaze_tracker, head_pose, liveness,
              face_detector, level_colors,
              obj_detector=None):
    """Render the complete non-overlapping ProctorAI HUD onto frame."""
    import cv2, numpy as np, time
    from config import SESSION_ID, BANNED_OBJECT_CLASSES

    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # BGR colour palette ──────────────────────────────────────────────────
    C_BG    = ( 18,  18,  18)
    C_TITLE = ( 36,  36,  36)
    C_RULE  = ( 55,  55,  55)
    C_DIM   = (110, 110, 110)    # dim label/unit text
    C_TEXT  = (210, 210, 210)    # normal value text
    C_HEAD  = (100, 150, 200)    # section header (steel blue)
    C_OK    = ( 60, 190,  60)    # green  — normal
    C_WARN  = ( 30, 145, 235)    # amber  — minor flag
    C_BAD   = ( 55,  55, 215)    # red    — serious
    C_IRIS  = ( 30, 195, 220)    # iris dots
    C_FACE  = ( 50, 200,  50)    # face box

    RISK_THEME = {
        "LOW":    (( 25, 100,  25), ( 70, 220,  70)),   # (badge_bg, badge_txt)
        "MEDIUM": (( 20,  85, 160), ( 70, 170, 240)),
        "HIGH":   (( 30,  30, 155), ( 80,  90, 235)),
    }

    SIDEBAR_W = 200
    ALPHA     = 0.70

    # helpers ─────────────────────────────────────────────────────────────
    def _t(text, x, y, color=C_TEXT, scale=0.42, thick=1):
        cv2.putText(frame, str(text), (x, y), FONT,
                    scale, color, thick, cv2.LINE_AA)

    def _row(label, value, lx, ly, vc=C_TEXT):
        """Dim label left, coloured value right."""
        _t(label, lx, ly, C_DIM,  0.38)
        _t(value, lx + 90, ly, vc, 0.42)

    def _sec(title, lx, ly):
        """Section separator rule + header."""
        cv2.line(frame, (lx, ly), (SIDEBAR_W - 6, ly), C_RULE, 1)
        _t(title, lx, ly + 13, C_HEAD, 0.40, 1)
        return ly + 21

    def _sc(flag, warn=False):
        if flag: return C_BAD
        if warn: return C_WARN
        return C_OK

    # 1. Dark sidebar ─────────────────────────────────────────────────────
    ov = frame.copy()
    cv2.rectangle(ov, (0, 0), (SIDEBAR_W, h), C_BG, -1)
    cv2.addWeighted(ov, ALPHA, frame, 1 - ALPHA, 0, frame)
    cv2.line(frame, (SIDEBAR_W, 0), (SIDEBAR_W, h), C_RULE, 1)

    # Title bar
    cv2.rectangle(frame, (0, 0), (SIDEBAR_W, 24), C_TITLE, -1)
    _t("ProctorAI", 8, 17, C_TEXT, 0.50, 1)

    # 2. Live data ─────────────────────────────────────────────────────────
    snap    = risk_engine.get_snapshot()
    score   = snap["risk_score"]
    level   = snap["risk_level"]
    counts  = snap.get("signal_counts", {})
    flagged = set(snap.get("flagged_signals", []))

    yaw    = getattr(head_pose, "last_yaw",        0.0)
    pitch  = getattr(head_pose, "last_pitch",      0.0)
    roll   = getattr(head_pose, "last_roll",       0.0)
    viols  = getattr(head_pose, "violation_count", 0)

    blinks    = getattr(liveness, "blink_count", 0)
    eye_cl    = getattr(liveness, "eye_closed",  False)
    elmin     = (time.time() - liveness.session_start) / 60.0
    brate     = round(blinks / elmin, 1) if elmin > 0.1 else 0.0
    off_pct   = gaze_tracker.get_offscreen_pct()

    # 3. Sidebar sections ──────────────────────────────────────────────────
    X = 8
    y = 30

    # HEAD POSE
    y = _sec("HEAD POSE", X, y)
    _row("Yaw",        f"{yaw:+.1f} deg",   X, y, _sc(False, abs(yaw) > 15));   y += 16
    _row("Pitch",      f"{pitch:+.1f} deg", X, y, _sc(False, abs(pitch) > 15)); y += 16
    _row("Roll",       f"{roll:+.1f} deg",  X, y, _sc(False, abs(roll) > 20));  y += 16
    _row("Violations", str(viols),          X, y, _sc(viols >= 8, viols >= 3)); y += 20

    # GAZE
    y = _sec("GAZE", X, y)
    _row("Off-screen",  f"{off_pct:.1f}%", X, y, _sc(off_pct > 40, off_pct > 20)); y += 20

    # LIVENESS
    y = _sec("LIVENESS", X, y)
    _row("Eye",        "CLOSED" if eye_cl else "OPEN", X, y,
         C_BAD if eye_cl else C_OK); y += 16
    _row("Blinks",     str(blinks),           X, y, C_TEXT); y += 16
    _row("Rate",       f"{brate}/min",         X, y, _sc(False, not (8 <= brate <= 30))); y += 20

    # OBJECTS
    y = _sec("OBJECTS", X, y)
    if obj_detector is not None and obj_detector._model_ready:
        stats = obj_detector.get_stats()
        last  = stats["last_detections"]
        if last:
            for d in last[:3]:   # show up to 3 detected objects
                flag = d["label"] in BANNED_OBJECT_CLASSES
                _row(d["label"], f"{d['conf']*100:.0f}%", X, y,
                     C_BAD if flag else C_WARN)
                y += 15
        else:
            _t("None detected", X + 4, y + 1, C_OK, 0.38)
            y += 14
    else:
        _t("Loading model...", X + 4, y + 1, C_DIM, 0.36)
        y += 14
    y += 4

    # SIGNALS
    y = _sec("SIGNALS", X, y)
    SIGS = [("gaze_offscreen","Gaze"),("head_pose","Head"),
            ("liveness_fail","Live"),("audio_anomaly","Audio"),
            ("deepfake","Fake"),("banned_object","Object")]
    for key, lbl in SIGS:
        cnt  = counts.get(key, 0)
        flag = key in flagged
        tag  = " !" if flag else ""
        _row(lbl, f"{cnt}{tag}", X, y, _sc(flag, cnt > 0))
        y += 15

    # 4. Face box ──────────────────────────────────────────────────────────
    try:
        import face_recognition
        rgb_f = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        for (top, right, bottom, left) in face_recognition.face_locations(rgb_f):
            cv2.rectangle(frame, (left, top), (right, bottom), C_FACE, 2)
    except Exception:
        pass

    # 5. Iris dots ─────────────────────────────────────────────────────────
    try:
        rgb_g  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res    = gaze_tracker.face_mesh.process(rgb_g)
        if res.multi_face_landmarks:
            lms = res.multi_face_landmarks[0].landmark
            def _ic(ids):
                pts = [(int(lms[i].x * w), int(lms[i].y * h)) for i in ids]
                return (int(np.mean([p[0] for p in pts])),
                        int(np.mean([p[1] for p in pts])))
            cv2.circle(frame, _ic(gaze_tracker.LEFT_IRIS),  4, C_IRIS, -1)
            cv2.circle(frame, _ic(gaze_tracker.RIGHT_IRIS), 4, C_IRIS, -1)
    except Exception:
        pass

    # 6. Risk badge (top-right) — 3 separate lines, nothing overlaps ───────
    bg_col, fg_col = RISK_THEME.get(level, ((45, 45, 45), C_TEXT))
    BW, BH = 148, 56
    bx = w - BW - 10
    by = 10

    ov2 = frame.copy()
    cv2.rectangle(ov2, (bx, by), (bx + BW, by + BH), bg_col, -1)
    cv2.addWeighted(ov2, 0.82, frame, 0.18, 0, frame)
    cv2.rectangle(frame, (bx, by), (bx + BW, by + BH), fg_col, 1)

    # Row 1: tiny "RISK SCORE" label
    cv2.putText(frame, "RISK SCORE", (bx + 8, by + 13),
                FONT, 0.31, fg_col, 1, cv2.LINE_AA)
    # Row 2: big score
    cv2.putText(frame, f"{score}/100", (bx + 8, by + 33),
                FONT, 0.64, fg_col, 2, cv2.LINE_AA)
    # Row 3: level tag
    cv2.putText(frame, level, (bx + 8, by + 50),
                FONT, 0.38, fg_col, 1, cv2.LINE_AA)

    # 7. Footer bar ────────────────────────────────────────────────────────
    FH = 22
    fov = frame.copy()
    cv2.rectangle(fov, (0, h - FH), (w, h), C_BG, -1)
    cv2.addWeighted(fov, 0.78, frame, 0.22, 0, frame)
    cv2.line(frame, (0, h - FH), (w, h - FH), C_RULE, 1)

    footer = (f"Session: {SESSION_ID}    "
              f"Frame: {frame_count}    "
              f"Events: {snap.get('total_events', 0)}    "
              f"Conf: {snap.get('confidence', 0.0):.2f}")
    cv2.putText(frame, footer, (SIDEBAR_W + 10, h - 6),
                FONT, 0.36, C_DIM, 1, cv2.LINE_AA)



def main():
    print(f"\n── ProctorAI ── Session: {SESSION_ID} ──────────────────\n")

    # ─────────────────────────────────────────────────────────────────────
    # 1. Init Risk Engine + Temporal Analyzer first
    #    (needed before we can build the on_event callback)
    # ─────────────────────────────────────────────────────────────────────
    risk_engine = RiskEngine()

    # Temporal analyzer fires its own events of type "temporal".
    # These go directly to risk_engine — NOT back through on_event
    # (that would re-add them to temporal_analyzer → infinite loop).
    temporal_analyzer = TemporalAnalyzer(
        event_callback = lambda e: risk_engine.process_event(e),
        weights_path   = "ml_models/weights/temporal_lstm.pth",
    )

    # Build the central callback — used by all other modules
    on_event = make_on_event(risk_engine, temporal_analyzer)

    # ─────────────────────────────────────────────────────────────────────
    # 2. Init vision modules (per-frame, synchronous)
    # ─────────────────────────────────────────────────────────────────────
    face_detector = FaceDetector()
    gaze_tracker  = GazeTracker()
    head_pose     = HeadPoseEstimator()
    liveness      = LivenessDetector()
    obj_detector  = ObjectDetector(event_callback=on_event)

    # ─────────────────────────────────────────────────────────────────────
    # 3. Init background modules (async, event-driven)
    # ─────────────────────────────────────────────────────────────────────
    keystroke = KeystrokeMonitor(event_callback=on_event)
    mouse_mon = MouseMonitor(event_callback=on_event)
    window_mon = WindowMonitor(event_callback=on_event)
    audio     = AudioMonitor(event_callback=on_event)
    deepfake  = DeepfakeDetector(
        event_callback = on_event,
        weights_path   = None,   # None = ImageNet pretrained base
                                 # Swap for your fine-tuned weights path
    )

    # ─────────────────────────────────────────────────────────────────────
    # 4. Open webcam
    # ─────────────────────────────────────────────────────────────────────
    print("[main] Opening webcam...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          FPS)

    if not cap.isOpened():
        print(
            "[main] ERROR: Cannot open webcam.\n"
            "       Check CAMERA_INDEX in config.py (currently: "
            f"{CAMERA_INDEX})"
        )
        sys.exit(1)

    print(f"[main] Webcam opened — {FRAME_WIDTH}×{FRAME_HEIGHT} @ {FPS}fps")

    # ─────────────────────────────────────────────────────────────────────
    # 5. Capture baseline face (MUST happen before main loop)
    # ─────────────────────────────────────────────────────────────────────
    if not capture_baseline(cap, face_detector):
        print("[main] Baseline capture cancelled — exiting")
        cap.release()
        sys.exit(0)

    # ─────────────────────────────────────────────────────────────────────
    # 6. Start all background threads
    # All three pynput/PyAudio modules require macOS permissions.
    # Set the ENABLE_* flags to True ONLY after granting:
    #   KEYSTROKE + MOUSE → Input Monitoring in System Settings
    #   AUDIO             → Microphone in System Settings
    # ─────────────────────────────────────────────────────────────────────
    if ENABLE_KEYSTROKE:
        safe_start(keystroke, "KeystrokeMonitor", liveness_check=True)
    else:
        print("  [main] KeystrokeMonitor disabled  — set ENABLE_KEYSTROKE=True after")
        print("         granting: System Settings > Privacy & Security > Input Monitoring > add Terminal\n")

    if ENABLE_MOUSE:
        safe_start(mouse_mon, "MouseMonitor", liveness_check=True)
    else:
        print("  [main] MouseMonitor disabled       — set ENABLE_MOUSE=True after")
        print("         granting: System Settings > Privacy & Security > Input Monitoring > add Terminal\n")

    safe_start(window_mon, "WindowMonitor")

    if ENABLE_AUDIO:
        safe_start(audio, "AudioMonitor", liveness_check=True)
    else:
        print("  [main] AudioMonitor disabled       — set ENABLE_AUDIO=True after")
        print("         granting: System Settings > Privacy & Security > Microphone > add Terminal\n")

    safe_start(deepfake,          "DeepfakeDetector")
    safe_start(temporal_analyzer, "TemporalAnalyzer")
    safe_start(obj_detector,       "ObjectDetector")
    start_process_monitor(on_event)

    print("[main] Running — press Ctrl+C or 'q' to stop\n")

    # ─────────────────────────────────────────────────────────────────────
    # 7. Graceful shutdown handler
    # ─────────────────────────────────────────────────────────────────────
    running = {"active": True}

    def shutdown(sig=None, frame=None):
        if not running["active"]:
            return          # prevent double-shutdown
        running["active"] = False

        print("\n\n[main] Shutting down all modules...")
        try:
            keystroke.stop()
            mouse_mon.stop()
            window_mon.stop()
            audio.stop()
            deepfake.stop()
            temporal_analyzer.stop()
            obj_detector.stop()
            # Release MediaPipe face mesh resources
            gaze_tracker.release()
            head_pose.release()
            liveness.release()
            # FaceDetector uses face_recognition — no .release() needed
        except Exception as e:
            print(f"[main] Shutdown error: {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()

        # ── Final session report ──────────────────────────────────────
        snap = risk_engine.get_snapshot()
        print(f"\n── Final Session Report ─────────────────────────────")
        print(f"  Session ID    : {SESSION_ID}")
        print(f"  Risk Score    : {snap['risk_score']} / 100")
        print(f"  Risk Level    : {snap['risk_level']}")
        print(f"  Confidence    : {snap['confidence']}")
        print(f"  Flagged       : {snap['flagged_signals']}")
        print(f"  Signal Counts : {snap['signal_counts']}")
        print(f"  Total Events  : {snap['total_events']}")
        print(f"  Session Time  : {snap['session_elapsed']}s")
        print(f"─────────────────────────────────────────────────────\n")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ─────────────────────────────────────────────────────────────────────
    # 8. Main webcam loop
    # ─────────────────────────────────────────────────────────────────────
    frame_delay  = 1.0 / FPS   # target seconds per frame
    frame_count  = 0
    read_errors  = 0

    # Risk level → overlay color map
    level_colors = {
        "LOW":    (0,   200,  0),
        "MEDIUM": (0,   165, 255),
        "HIGH":   (0,     0, 255),
    }

    while running["active"]:
        loop_start = time.time()

        # ── Read frame ────────────────────────────────────────────────
        ok, frame = cap.read()
        if not ok:
            read_errors += 1
            if read_errors >= 10:
                print("[main] Too many consecutive frame read failures — exiting")
                shutdown()
                break
            time.sleep(0.1)
            continue
        read_errors = 0
        frame_count += 1

        # ── Update deepfake detector with latest frame ─────────────────
        # (runs inference on its own timer, not every frame)
        deepfake.update_frame(frame)

        # ── Run all per-frame vision modules ──────────────────────────
        for module in [face_detector, gaze_tracker, head_pose, liveness, obj_detector]:
            try:
                events = module.process_frame(frame)
                for event in events:
                    on_event(event)
            except Exception as e:
                print(f"[main] {module.__class__.__name__} error: {e}")

        # ── Unified HUD Overlay ─────────────────────────────────
        if DEBUG_OVERLAY:
            _draw_hud(
                frame, frame_count, risk_engine,
                gaze_tracker, head_pose, liveness,
                face_detector, level_colors,
                obj_detector=obj_detector,
            )


        # ── Show frame ────────────────────────────────────────────────
        cv2.imshow("ProctorAI", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            shutdown()
            break

        # ── Frame rate limiter ─────────────────────────────────────────
        # Ensures we don't spin faster than target FPS
        elapsed = time.time() - loop_start
        remaining = frame_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)


if __name__ == "__main__":
    main()
