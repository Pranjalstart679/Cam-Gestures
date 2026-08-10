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
