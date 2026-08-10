"""Resolution-independent cursor coordinate mapping and smoothing."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ControlRegion:
    """The normalized camera area that maps to the full desktop."""

    left: float = 0.20
    top: float = 0.20
    right: float = 0.80
    bottom: float = 0.80

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in values):
            raise ValueError("Control-region values must be finite normalized coordinates (0 to 1).")
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("Control region must have positive width and height.")


@dataclass(frozen=True, slots=True)
class ScreenPoint:
    """An integer screen coordinate suitable for a mouse backend."""

    x: int
    y: int


class CursorMapper:
    """Map normalized hand landmarks into bounded desktop coordinates."""

    def __init__(self, screen_width: int, screen_height: int, region: ControlRegion) -> None:
        if screen_width < 1 or screen_height < 1:
            raise ValueError("Screen dimensions must be positive.")
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._region = region

    def map(self, normalized_x: float, normalized_y: float) -> ScreenPoint:
        """Clamp a normalized camera coordinate and map it to the full screen."""
        if not isfinite(normalized_x) or not isfinite(normalized_y):
            raise ValueError("Landmark coordinates must be finite.")

        clamped_x = min(max(normalized_x, self._region.left), self._region.right)
        clamped_y = min(max(normalized_y, self._region.top), self._region.bottom)
        relative_x = (clamped_x - self._region.left) / (self._region.right - self._region.left)
        relative_y = (clamped_y - self._region.top) / (self._region.bottom - self._region.top)
        return ScreenPoint(
            x=round(relative_x * (self._screen_width - 1)),
            y=round(relative_y * (self._screen_height - 1)),
        )


class ExponentialSmoother:
    """Low-latency exponential moving average for successive cursor targets."""

    def __init__(self, retention: float = 0.70) -> None:
        if not 0.0 <= retention < 1.0:
            raise ValueError("Smoothing retention must be at least 0 and less than 1.")
        self._retention = retention
        self._value: tuple[float, float] | None = None

    def update(self, target: ScreenPoint) -> ScreenPoint:
        """Return the first target directly, then smooth following targets."""
        if self._value is None:
            self._value = (float(target.x), float(target.y))
        else:
            previous_x, previous_y = self._value
            weight = 1.0 - self._retention
            self._value = (
                self._retention * previous_x + weight * target.x,
                self._retention * previous_y + weight * target.y,
            )
        return ScreenPoint(round(self._value[0]), round(self._value[1]))

    def reset(self) -> None:
        """Discard history after the hand leaves the frame."""
        self._value = None
