"""Map transcribed speech to session events without touching the microphone."""

from __future__ import annotations

import re

from core.constants import SessionEvent


def normalize_phrase(phrase: str) -> str:
    """Lowercase a phrase and collapse punctuation into single spaces."""
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", phrase.lower())
    return " ".join(cleaned.split())


class PhraseMatcher:
    """Match whole phrases inside a transcript using word boundaries."""

    def __init__(self, wake_phrase: str, stop_phrase: str, quit_phrase: str = "quit") -> None:
        self.wake_phrase = normalize_phrase(wake_phrase)
        self.stop_phrase = normalize_phrase(stop_phrase)
        self.quit_phrase = normalize_phrase(quit_phrase)
        if not self.wake_phrase or not self.stop_phrase or not self.quit_phrase:
            raise ValueError("Voice phrases must contain at least one letter or number.")
        if len({self.wake_phrase, self.stop_phrase, self.quit_phrase}) < 3:
            raise ValueError("Wake, stop, and quit phrases must be distinct.")

    def match(self, transcript: str) -> SessionEvent:
        """Return the highest-priority command found in ``transcript``."""
        text = normalize_phrase(transcript)
        if not text:
            return SessionEvent.NONE
        if self._contains(text, self.quit_phrase):
            return SessionEvent.QUIT
        if self._contains(text, self.stop_phrase):
            return SessionEvent.DEACTIVATE
        if self._contains(text, self.wake_phrase):
            return SessionEvent.ACTIVATE
        return SessionEvent.NONE

    @staticmethod
    def _contains(text: str, phrase: str) -> bool:
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
