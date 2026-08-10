"""Predictable application-state transitions for gesture-control actions."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from core.constants import AppState
from vision.gesture_detector import Gesture


@dataclass(frozen=True, slots=True)
class StateTransition:
    """A state update plus explicit drag edge events for the action layer."""

    previous: AppState
    current: AppState
    start_drag: bool = False
    end_drag: bool = False


class StateManager:
    """Debounce fist entry and coordinate activity, scrolling, and cooldown modes."""

    def __init__(self, fist_confirmation_frames: int = 3, cooldown_seconds: float = 0.20) -> None:
        if fist_confirmation_frames < 1:
            raise ValueError("Fist confirmation requires at least one frame.")
        if cooldown_seconds < 0:
            raise ValueError("Cooldown cannot be negative.")
        self._fist_confirmation_frames = fist_confirmation_frames
        self._cooldown_seconds = cooldown_seconds
        self._state = AppState.IDLE
        self._fist_frames = 0
        self._cooldown_until = 0.0

    @property
    def state(self) -> AppState:
        """Return the current application state."""
        return self._state

    def update(self, gesture: Gesture, now: float | None = None) -> StateTransition:
        """Advance the state machine for one recognized gesture frame."""
        current_time = monotonic() if now is None else now
        previous = self._state

        if self._state is AppState.COOLDOWN:
            if current_time < self._cooldown_until:
                self._fist_frames = 0
                return StateTransition(previous, self._state)
            self._state = AppState.IDLE
            previous = AppState.COOLDOWN

        if self._state is AppState.DRAGGING:
            if gesture is Gesture.FIST:
                return StateTransition(previous, self._state)
            self._state = self._base_state(gesture)
            self._fist_frames = 0
            return StateTransition(previous, self._state, end_drag=True)

        if gesture is Gesture.FIST:
            self._fist_frames += 1
            if self._fist_frames >= self._fist_confirmation_frames:
                self._state = AppState.DRAGGING
                return StateTransition(previous, self._state, start_drag=True)
            self._state = AppState.ACTIVE
            return StateTransition(previous, self._state)

        self._fist_frames = 0
        self._state = self._base_state(gesture)
        return StateTransition(previous, self._state)

    def begin_cooldown(self, now: float | None = None) -> None:
        """Enter post-click cooldown after a confirmed pinch action."""
        current_time = monotonic() if now is None else now
        self._state = AppState.COOLDOWN
        self._cooldown_until = current_time + self._cooldown_seconds
        self._fist_frames = 0

    def force_idle(self) -> StateTransition:
        """Stop pending gesture state, releasing a drag if one was active."""
        previous = self._state
        was_dragging = previous is AppState.DRAGGING
        self._state = AppState.IDLE
        self._fist_frames = 0
        return StateTransition(previous, self._state, end_drag=was_dragging)

    @staticmethod
    def _base_state(gesture: Gesture) -> AppState:
        if gesture is Gesture.NONE:
            return AppState.IDLE
        if gesture is Gesture.TWO_FINGER:
            return AppState.SCROLLING
        return AppState.ACTIVE
