"""OpenCV debug overlay for observing gesture-control behavior."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class DebugInfo:
    """The values rendered in the compact runtime debug overlay."""

    hand_detected: bool
    gesture: str
    state: str
    fingertip: tuple[float, float] | None
    pinch_ratio: float | None
    cursor_label: str
    action_label: str


class DebugOverlay:
    """Calculate a smoothed FPS value and render diagnostics directly on frames."""

    def __init__(self) -> None:
        self._previous_time: float | None = None
        self._fps = 0.0

    def update_fps(self, now: float | None = None) -> float:
        """Return an exponentially smoothed frames-per-second estimate."""
        current_time = monotonic() if now is None else now
        if self._previous_time is not None:
            elapsed = current_time - self._previous_time
            if elapsed > 0:
                instantaneous_fps = 1.0 / elapsed
                self._fps = instantaneous_fps if self._fps == 0 else 0.85 * self._fps + 0.15 * instantaneous_fps
        self._previous_time = current_time
        return self._fps

    def draw(self, frame: np.ndarray, info: DebugInfo) -> None:
        """Draw diagnostic values on the upper-left corner of an OpenCV BGR frame."""
        fps = self.update_fps()
        fingertip_text = "n/a" if info.fingertip is None else f"{info.fingertip[0]:.3f}, {info.fingertip[1]:.3f}"
        pinch_text = "n/a" if info.pinch_ratio is None else f"{info.pinch_ratio:.3f}"
        lines = (
            f"FPS: {fps:.1f}",
            f"Hand: {'yes' if info.hand_detected else 'no'} | Gesture: {info.gesture}",
            f"State: {info.state} | Tip: {fingertip_text}",
            f"Pinch ratio: {pinch_text}",
            info.cursor_label,
            info.action_label,
        )
        panel_height = 28 + 25 * len(lines)
        cv2.rectangle(frame, (6, 6), (530, panel_height), (20, 20, 20), -1)
        for index, line in enumerate(lines):
            cv2.putText(
                frame,
                line,
                (14, 30 + 25 * index),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
