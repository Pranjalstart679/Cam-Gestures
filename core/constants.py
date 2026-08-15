"""Shared application state definitions."""

from __future__ import annotations

from enum import Enum, auto


class AppState(Enum):
    """The currently active gesture-control mode."""

    IDLE = auto()
    ACTIVE = auto()
    DRAGGING = auto()
    SCROLLING = auto()
    COOLDOWN = auto()


class SessionMode(Enum):
    """Whether the webcam session is waiting or running."""

    LISTENING = auto()
    ACTIVE = auto()


class SessionEvent(Enum):
    """User or voice events that change the session lifecycle."""

    NONE = auto()
    ACTIVATE = auto()
    DEACTIVATE = auto()
    QUIT = auto()
