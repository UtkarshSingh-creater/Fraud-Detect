"""
Dependency check script for proctorAI
Run: python check_deps.py
"""

packages = [
    ("cv2",            "opencv-python"),
    ("mediapipe",      "mediapipe"),
    ("face_recognition", "face-recognition"),
    ("dlib",           "dlib"),
    ("torch",          "torch"),
    ("torchvision",    "torchvision"),
    ("numpy",          "numpy"),
    ("sklearn",        "scikit-learn"),
    ("pyaudio",        "pyaudio"),
    ("librosa",        "librosa"),
    ("webrtcvad",      "webrtcvad"),
    ("pynput",         "pynput"),
    ("websockets",     "websockets"),
    ("dotenv",         "python-dotenv"),
    ("PIL",            "pillow"),
    ("scipy",          "scipy"),
]

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"
BOLD  = "\033[1m"

print(f"\n{BOLD}{'Package':<20} {'Import':<22} {'Status'}{RESET}")
print("-" * 55)

passed, failed = 0, 0
for import_name, pkg_name in packages:
    try:
        mod = __import__(import_name)
        version = getattr(mod, "__version__", "n/a")
        print(f"{pkg_name:<20} {import_name:<22} {GREEN}✓  {version}{RESET}")
        passed += 1
    except ImportError as e:
        print(f"{pkg_name:<20} {import_name:<22} {RED}✗  MISSING — {e}{RESET}")
        failed += 1

print("-" * 55)
print(f"\n{BOLD}Results: {GREEN}{passed} passed{RESET}{BOLD}, {RED}{failed} failed{RESET}\n")
