"""Background microphone listener using an offline Vosk model."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from core.constants import SessionEvent
from voice.commands import PhraseMatcher


class VoiceError(RuntimeError):
    """Raised when the microphone listener cannot start."""


class VoiceListener:
    """Capture 16 kHz mono audio and emit session events from recognized phrases."""

    def __init__(self, matcher: PhraseMatcher, model_path: Path, sample_rate: int = 16000) -> None:
        self._matcher = matcher
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._events: queue.Queue[SessionEvent] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_transcript = ""

    def start(self) -> None:
        """Open the microphone on a daemon thread."""
        if self._thread is not None:
            return
        if not self._model_path.exists():
            raise VoiceError(
                f"Vosk model not found at {self._model_path}. "
                "Download a small English model into that folder (see README)."
            )
        try:
            import sounddevice  # noqa: F401
            from vosk import KaldiRecognizer, Model
        except ImportError as error:
            raise VoiceError(
                "Voice activation requires vosk and sounddevice. Run pip install -r requirements.txt."
            ) from error

        try:
            model = Model(str(self._model_path))
        except Exception as error:  # vosk raises generic exceptions for bad models
            raise VoiceError(f"Unable to load Vosk model at {self._model_path}: {error}") from error

        recognizer = KaldiRecognizer(model, self._sample_rate)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(recognizer,),
            name="voice-listener",
            daemon=True,
        )
        self._thread.start()

    def poll(self) -> SessionEvent:
        """Return the newest pending command, or ``NONE`` if the queue is empty."""
        event = SessionEvent.NONE
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return event

    def stop(self) -> None:
        """Ask the listener thread to exit and wait briefly for it."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _run(self, recognizer: object) -> None:
        import sounddevice as sd

        audio_queue: queue.Queue[bytes] = queue.Queue()

        def callback(indata: bytes, frames: int, time_info: object, status: object) -> None:
            if status:
                return
            audio_queue.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop.is_set():
                    try:
                        data = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    accept = getattr(recognizer, "AcceptWaveform")
                    if accept(data):
                        payload = json.loads(getattr(recognizer, "Result")())
                        transcript = str(payload.get("text") or "").strip()
                        if transcript:
                            self.last_transcript = transcript
                            event = self._matcher.match(transcript)
                            if event is not SessionEvent.NONE:
                                self._events.put(event)
                    else:
                        payload = json.loads(getattr(recognizer, "PartialResult")())
                        partial = str(payload.get("partial") or "").strip()
                        if partial:
                            self.last_transcript = partial
        except Exception as error:
            self.last_transcript = f"microphone error: {error}"
