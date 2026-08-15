"""Explicit, guarded mappings from semantic gestures to mouse actions."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from vision.gesture_detector import Gesture, GestureObservation


class MouseActions(Protocol):
    """Mouse operations used by pinch-click and two-finger scroll."""

    def click(self) -> None: ...

    def scroll(self, amount: int) -> None: ...


class PinchClickGate:
    """Confirm a pinch over multiple frames and latch it until fingers separate."""

    def __init__(self, confirmation_frames: int = 3, cooldown_seconds: float = 0.20) -> None:
        if confirmation_frames < 1:
            raise ValueError("Pinch confirmation requires at least one frame.")
        if cooldown_seconds < 0:
            raise ValueError("Pinch cooldown cannot be negative.")
        self._confirmation_frames = confirmation_frames
        self._cooldown_seconds = cooldown_seconds
        self._frames = 0
        self._latched = False
        self._cooldown_until = 0.0

    def update(self, is_pinching: bool, now: float | None = None) -> bool:
        """Return ``True`` exactly once for each confirmed pinch entry."""
        current_time = monotonic() if now is None else now
        if not is_pinching:
            self._frames = 0
            self._latched = False
            return False
        if self._latched:
            return False

        self._frames += 1
        if self._frames < self._confirmation_frames or current_time < self._cooldown_until:
            return False

        self._latched = True
        self._cooldown_until = current_time + self._cooldown_seconds
        return True


class ScrollAccumulator:
    """Turn relative two-finger vertical motion into discrete scroll steps."""

    def __init__(self, sensitivity: float = 1.0) -> None:
        if sensitivity <= 0:
            raise ValueError("Scroll sensitivity must be positive.")
        self._sensitivity = sensitivity
        self._previous_y: float | None = None
        self._remainder = 0.0

    def update(self, normalized_y: float) -> int:
        """Return scroll steps; upward hand motion produces positive scrolling."""
        if self._previous_y is None:
            self._previous_y = normalized_y
            return 0

        delta = self._previous_y - normalized_y
        self._previous_y = normalized_y
        self._remainder += delta * 100 * self._sensitivity
        steps = int(self._remainder)
        self._remainder -= steps
        return max(-10, min(10, steps))

    def reset(self) -> None:
        """Start a fresh scroll gesture without carrying prior movement."""
        self._previous_y = None
        self._remainder = 0.0


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Feedback for the debug overlay."""

    clicked: bool = False
    scroll_amount: int = 0


class GestureActionRouter:
    """Apply only the explicit Phase 4 and 5 gesture mappings."""

    def __init__(
        self,
        mouse: MouseActions,
        pinch_confirmation_frames: int = 3,
        click_cooldown_seconds: float = 0.20,
        scroll_sensitivity: float = 1.0,
    ) -> None:
        self._mouse = mouse
        self._pinch_gate = PinchClickGate(pinch_confirmation_frames, click_cooldown_seconds)
        self._scroll = ScrollAccumulator(scroll_sensitivity)

    def update(self, observation: GestureObservation | None, now: float | None = None) -> ActionResult:
        """Handle one observation and return the action performed, if any."""
        is_pinching = observation is not None and observation.gesture is Gesture.PINCH
        clicked = self._pinch_gate.update(is_pinching, now)
        if clicked:
            self._mouse.click()

        if observation is None or observation.gesture is not Gesture.TWO_FINGER:
            self._scroll.reset()
            return ActionResult(clicked=clicked)

        amount = self._scroll.update(observation.scroll_anchor_y)
        if amount:
            self._mouse.scroll(amount)
        return ActionResult(clicked=clicked, scroll_amount=amount)
