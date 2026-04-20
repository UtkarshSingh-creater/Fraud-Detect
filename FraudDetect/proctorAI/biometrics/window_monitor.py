# ─────────────────────────────────────────────────────
# biometrics/window_monitor.py
# Detects window/app focus changes
# Works on macOS, Windows, and Linux
# ─────────────────────────────────────────────────────

import time
import threading
import platform
import sys

OS = platform.system()   # "Darwin", "Windows", "Linux"


class WindowMonitor:
    def __init__(self, event_callback):
        self.event_callback   = event_callback
        self.is_running       = False
        self.thread           = None
        self.last_app         = None
        self.switch_count     = 0
        self.last_switch_time = None
        self._detected_suspicious = set()  # track already-reported suspicious apps

        # Apps allowed during interview
        self.ALLOWED_APPS = [
            "zoom", "skype", "teams", "meet",
            "antigravity", "finder",
            "linkednotesuiservice",
            "quicklookuiservice",
            "sharesheetui",
            "autofill",
            "themewidgetcontrolviewservice",
            "open and save panel service",
            "controlcentre",
            "notificationcentre",
            "systempreferences",
            "systemsettings",
            "python",           # interview coding environment
            "terminal",         # interview coding environment
            "iterm2",
            "xcode",
            "vscode",
            "code",
        ]

        self.SUSPICIOUS_APPS = [
            "chatgpt",
            "claude",
            "safari",
            "chrome",
            "firefox",
            "notion",
            "whatsapp",
            "telegram",
            "messages",
            "notes",
            "textedit",
            "notepad",
            "edge",
            "brave",
            "opera",
            "perplexity",
            "copilot",
        ]

    # ── Start ────────────────────────────────────────────────────────────
    def start(self):
        self.is_running = True
        self.thread     = threading.Thread(
            target = self._monitor_loop,
            daemon = True,
        )
        self.thread.start()
        print(f"[WindowMonitor] Started on {OS} — monitoring window focus")

    # ── Stop ─────────────────────────────────────────────────────────────
    def stop(self):
        self.is_running = False
        print("[WindowMonitor] Stopped")

    # ── Main loop — picks correct method per OS ───────────────────────────
    def _monitor_loop(self):
        if OS == "Darwin":
            self._loop_macos()
        elif OS == "Windows":
            self._loop_windows()
        elif OS == "Linux":
            self._loop_linux()
        else:
            print(f"[WindowMonitor] Unsupported OS: {OS}")

    # ── macOS ─────────────────────────────────────────────────────────────
    def _loop_macos(self):
        try:
            from AppKit import NSWorkspace
            import subprocess
        except ImportError:
            print("[WindowMonitor] Install: pip install pyobjc-framework-Cocoa")
            return

        while self.is_running:
            try:
                # Check focused app
                workspace  = NSWorkspace.sharedWorkspace()
                active_app = workspace.activeApplication()
                app_name   = active_app.get(
                    "NSApplicationName", ""
                ).lower() if active_app else ""

                if app_name and app_name != self.last_app:
                    self._handle_switch(app_name)
                    self.last_app = app_name

                # Also check ALL running apps for suspicious ones
                # This catches floating windows and background apps
                running_apps = workspace.runningApplications()
                for app in running_apps:
                    name = (app.localizedName() or "").lower()
                    if any(s in name for s in self.SUSPICIOUS_APPS):
                        if name not in self._detected_suspicious:
                            self._detected_suspicious.add(name)
                            self._send_event({
                                "type":          "tab_switch",
                                "flagged":       True,
                                "app_name":      name,
                                "switch_count":  self.switch_count,
                                "duration_ms":   0,
                                "is_suspicious": True,
                                "message":       f"Suspicious app running: {name} (floating window possible)",
                                "timestamp":     time.time(),
                            })

            except Exception as e:
                print(f"[WindowMonitor] macOS error: {e}")

            time.sleep(0.5)

    # ── Windows ───────────────────────────────────────────────────────────
    def _loop_windows(self):
        try:
            import win32gui
            import win32process
            import psutil
        except ImportError:
            print("[WindowMonitor] Install: pip install pywin32 psutil")
            return

        while self.is_running:
            try:
                hwnd    = win32gui.GetForegroundWindow()
                _, pid  = win32process.GetWindowThreadProcessId(hwnd)
                proc    = psutil.Process(pid)
                app_name = proc.name().lower().replace(".exe", "")

                if app_name and app_name != self.last_app:
                    self._handle_switch(app_name)
                    self.last_app = app_name

            except Exception as e:
                print(f"[WindowMonitor] Windows error: {e}")

            time.sleep(0.5)

    # ── Linux ─────────────────────────────────────────────────────────────
    def _loop_linux(self):
        try:
            import subprocess
        except ImportError:
            return

        while self.is_running:
            try:
                # xdotool gets active window name on Linux
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output = True,
                    text           = True,
                )
                app_name = result.stdout.strip().lower()

                if app_name and app_name != self.last_app:
                    self._handle_switch(app_name)
                    self.last_app = app_name

            except Exception as e:
                print(f"[WindowMonitor] Linux error: {e}")

            time.sleep(0.5)

    # ── Handle switch event ───────────────────────────────────────────────
    def _handle_switch(self, new_app):
        now = time.time()
        self.switch_count += 1

        duration_ms = 0
        if self.last_switch_time:
            duration_ms = int((now - self.last_switch_time) * 1000)
        self.last_switch_time = now

        is_suspicious = any(s in new_app for s in self.SUSPICIOUS_APPS)
        is_allowed    = any(a in new_app for a in self.ALLOWED_APPS)
        flagged       = is_suspicious or (
            not is_allowed and self.switch_count > 2
        )

        self._send_event({
            "type":          "tab_switch",
            "flagged":       flagged,
            "app_name":      new_app,
            "switch_count":  self.switch_count,
            "duration_ms":   duration_ms,
            "is_suspicious": is_suspicious,
            "message": (
                f"Suspicious app opened: {new_app}"
                if is_suspicious else
                f"Window switched to: {new_app} (switch #{self.switch_count})"
            ),
            "timestamp": now,
        })

    # ── Stats ─────────────────────────────────────────────────────────────
    def get_stats(self):
        return {
            "switch_count": self.switch_count,
            "last_app":     self.last_app,
            "os":           OS,
        }

    # ── Send event ────────────────────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[WindowMonitor] Callback error: {e}")