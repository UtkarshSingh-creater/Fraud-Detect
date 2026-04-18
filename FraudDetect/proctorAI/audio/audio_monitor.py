# ─────────────────────────────────────────────────────
# audio/audio_monitor.py
# Module 7 — Audio Intelligence
# Detects multiple voices, whispering, noise anomalies
# ─────────────────────────────────────────────────────

import time
import threading
import numpy as np
import pyaudio
import webrtcvad
import librosa
from config import (
    AUDIO_SAMPLE_RATE,
    AUDIO_CHUNK_SIZE,
    AUDIO_CHANNELS,
    SPEAKER_COUNT_THRESHOLD,
    WHISPER_ENERGY_THRESHOLD,
    NOISE_ANOMALY_THRESHOLD,
)


class AudioMonitor:
    def __init__(self, event_callback):
        """
        event_callback: function that receives events
        e.g. def on_event(event): send_to_backend(event)
        """
        self.event_callback    = event_callback

        # PyAudio setup (deferred to start() so macOS permission check
        # only fires when audio monitoring is explicitly enabled)
        self.audio             = None
        self.stream            = None

        # WebRTC VAD — voice activity detection
        # aggressiveness 0-3 (3 = most aggressive filtering)
        self.vad               = webrtcvad.Vad(2)

        # Energy tracking
        self.energy_history    = []
        self.baseline_energy   = None
        self.baseline_ready    = False
        self.baseline_samples  = []
        self.session_start     = time.time()

        # Speaker tracking
        self.voice_segments    = []   # list of energy values during voice activity
        self.speaker_energies  = []   # energy clusters for multi-speaker detection

        # State
        self.is_running        = False
        self.thread            = None
        self.last_event_time   = time.time()

    # ── Start monitoring ─────────────────────────────────────────────────
    def start(self):
        """Start audio monitoring in background thread."""
        try:
            self.audio  = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format            = pyaudio.paInt16,
                channels          = AUDIO_CHANNELS,
                rate              = AUDIO_SAMPLE_RATE,
                input             = True,
                frames_per_buffer = AUDIO_CHUNK_SIZE,
            )
        except OSError as e:
            print(
                f"\n  [AudioMonitor] ⚠️  Failed to open microphone: {e}"
                f"\n                 Check System Settings → Privacy & Security → Microphone"
                f"\n                 and ensure Terminal.app is listed and enabled."
                f"\n                 Then Cmd+Q Terminal, reopen it, and try again.\n"
            )
            self.is_running = False
            return
        self.is_running = True
        self.thread     = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("[AudioMonitor] Started — monitoring audio")

        # Compute baseline after 30 seconds
        threading.Timer(30.0, self._compute_baseline).start()

    # ── Stop monitoring ──────────────────────────────────────────────────
    def stop(self):
        self.is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        print("[AudioMonitor] Stopped")

    # ── Main monitoring loop ─────────────────────────────────────────────
    def _monitor_loop(self):
        while self.is_running:
            try:
                raw = self.stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                self._process_chunk(raw)
            except Exception as e:
                print(f"[AudioMonitor] Stream error: {e}")
                break

    # ── Process each audio chunk ─────────────────────────────────────────
    def _process_chunk(self, raw_data):
        now = time.time()

        # Convert raw bytes to numpy array
        audio_array = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
        audio_norm  = audio_array / 32768.0   # normalize to -1.0 to 1.0

        # ── Calculate RMS energy ──────────────────────────────────────
        rms_energy  = float(np.sqrt(np.mean(audio_norm ** 2)))
        self.energy_history.append(rms_energy)

        # Keep last 300 samples (~10 seconds at default chunk size)
        if len(self.energy_history) > 300:
            self.energy_history.pop(0)

        # Add to baseline if still in baseline period
        elapsed = now - self.session_start
        if elapsed < 30.0:
            self.baseline_samples.append(rms_energy)

        # ── Voice activity detection (VAD) ────────────────────────────
        try:
            # WebRTC VAD needs 16-bit PCM at 16000Hz
            # Frame must be 10, 20 or 30ms
            frame_duration_ms = 20
            frame_size        = int(AUDIO_SAMPLE_RATE * frame_duration_ms / 1000) * 2
            frame             = raw_data[:frame_size]

            if len(frame) == frame_size:
                is_speech = self.vad.is_speech(frame, AUDIO_SAMPLE_RATE)
            else:
                is_speech = False
        except Exception:
            is_speech = rms_energy > 0.01

        # ── Collect voice segment energies ────────────────────────────
        if is_speech:
            self.voice_segments.append(rms_energy)
            if len(self.voice_segments) > 500:
                self.voice_segments.pop(0)

        # ── Only analyze and send events every 2 seconds ─────────────
        if now - self.last_event_time < 2.0:
            return
        self.last_event_time = now

        # ── Check for whispering ──────────────────────────────────────
        whisper_detected = (
            is_speech and
            rms_energy < WHISPER_ENERGY_THRESHOLD and
            rms_energy > 0.001   # not complete silence
        )

        # ── Check for noise anomaly ───────────────────────────────────
        noise_anomaly = False
        if self.baseline_ready and self.baseline_energy:
            if rms_energy > self.baseline_energy * NOISE_ANOMALY_THRESHOLD * 10:
                noise_anomaly = True

        # ── Detect multiple speakers ──────────────────────────────────
        multiple_speakers = False
        speaker_count     = 1

        if len(self.voice_segments) >= 50:
            speaker_count, multiple_speakers = self._detect_multiple_speakers()

        # ── Build and send event ──────────────────────────────────────
        flagged = whisper_detected or noise_anomaly or multiple_speakers
        message = self._get_message(whisper_detected, noise_anomaly, multiple_speakers, speaker_count)

        self._send_event({
            "type":              "audio",
            "rms_energy":        round(rms_energy, 4),
            "is_speech":         is_speech,
            "whisper_detected":  whisper_detected,
            "noise_anomaly":     noise_anomaly,
            "speaker_count":     speaker_count,
            "multiple_speakers": multiple_speakers,
            "flagged":           flagged,
            "message":           message,
            "timestamp":         now,
        })

    # ── Detect multiple speakers via energy clustering ───────────────────
    def _detect_multiple_speakers(self):
        """
        Uses energy level clustering to estimate speaker count.
        Different speakers tend to have different average energy levels.
        """
        try:
            samples = np.array(self.voice_segments[-100:])

            # Simple threshold-based clustering
            # Split into low/high energy — if both clusters have
            # enough samples, likely two different speakers
            mean_energy = np.mean(samples)
            low_energy  = samples[samples < mean_energy * 0.7]
            high_energy = samples[samples > mean_energy * 1.3]

            # If both clusters are substantial — two speakers
            if len(low_energy) > 25 and len(high_energy) > 25:
                return 2, True

            return 1, False

        except Exception:
            return 1, False

    # ── Compute baseline energy ──────────────────────────────────────────
    def _compute_baseline(self):
        if len(self.baseline_samples) >= 20:
            self.baseline_energy = float(np.mean(self.baseline_samples))
            self.baseline_ready  = True
            print(f"[AudioMonitor] Baseline computed: {self.baseline_energy:.4f} avg energy")
        else:
            print("[AudioMonitor] Not enough audio for baseline")

    # ── Get human readable message ───────────────────────────────────────
    def _get_message(self, whisper, noise, multi_speaker, count):
        if multi_speaker:
            return f"Multiple speakers detected — {count} voices in audio"
        if whisper:
            return "Whispering detected — possible assistance from someone nearby"
        if noise:
            return "Sudden noise anomaly — unexpected audio spike"
        return "Audio normal"

    # ── Get current stats ────────────────────────────────────────────────
    def get_stats(self):
        return {
            "avg_energy":      round(float(np.mean(self.energy_history)), 4) if self.energy_history else 0,
            "baseline_energy": round(self.baseline_energy, 4) if self.baseline_energy else None,
            "baseline_ready":  self.baseline_ready,
            "voice_samples":   len(self.voice_segments),
        }

    # ── Send event via callback ──────────────────────────────────────────
    def _send_event(self, event):
        try:
            self.event_callback(event)
        except Exception as e:
            print(f"[AudioMonitor] Callback error: {e}")