"""Idle/active session lifecycle so the camera can stay off until requested."""

from __future__ import annotations

from core.constants import SessionEvent, SessionMode


class SessionController:
    """Advance listen-first or immediate-camera sessions from explicit events."""

    def __init__(self, listen_first: bool) -> None:
        self.listen_first = listen_first
        self.mode = SessionMode.LISTENING if listen_first else SessionMode.ACTIVE
        self.running = True

    def handle(self, event: SessionEvent) -> SessionMode:
        """Apply one event and return the resulting mode."""
        if event is SessionEvent.NONE or not self.running:
            return self.mode

        if event is SessionEvent.QUIT:
            self.running = False
            return self.mode

        if not self.listen_first:
            if event is SessionEvent.DEACTIVATE:
                self.running = False
            return self.mode

        if event is SessionEvent.ACTIVATE and self.mode is SessionMode.LISTENING:
            self.mode = SessionMode.ACTIVE
        elif event is SessionEvent.DEACTIVATE and self.mode is SessionMode.ACTIVE:
            self.mode = SessionMode.LISTENING
        return self.mode
