"""Typed loading and validation of local gesture-control JSON configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from control.cursor import ControlRegion


class ConfigurationError(ValueError):
    """Raised when the local configuration file is missing or invalid."""


@dataclass(frozen=True, slots=True)
class CameraConfig:
    index: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class HandTrackingConfig:
    max_num_hands: int
    min_detection_confidence: float
    min_tracking_confidence: float


@dataclass(frozen=True, slots=True)
class CursorConfig:
    smoothing: float
    control_region: ControlRegion


@dataclass(frozen=True, slots=True)
class GestureConfig:
    pinch_threshold: float
    pinch_confirmation_frames: int
    cooldown_seconds: float
    scroll_sensitivity: float
    fist_confirmation_frames: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    camera: CameraConfig
    hand_tracking: HandTrackingConfig
    cursor: CursorConfig
    gestures: GestureConfig


def load_config(path: Path) -> AppConfig:
    """Load and validate the application's local JSON configuration file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON in configuration file {path}: {error.msg}") from error
    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration root must be a JSON object.")

    camera = _section(raw, "camera")
    tracking = _section(raw, "hand_tracking")
    cursor = _section(raw, "cursor")
    gestures = _section(raw, "gestures")
    try:
        region_values = cursor["control_region"]
        if not isinstance(region_values, list) or len(region_values) != 4:
            raise ConfigurationError("cursor.control_region must contain exactly four numbers.")
        return AppConfig(
            camera=CameraConfig(
                index=_integer(camera, "index", minimum=0),
                width=_integer(camera, "width", minimum=1),
                height=_integer(camera, "height", minimum=1),
            ),
            hand_tracking=HandTrackingConfig(
                max_num_hands=_integer(tracking, "max_num_hands", minimum=1),
                min_detection_confidence=_probability(tracking, "min_detection_confidence"),
                min_tracking_confidence=_probability(tracking, "min_tracking_confidence"),
            ),
            cursor=CursorConfig(
                smoothing=_number(cursor, "smoothing", minimum=0.0, maximum_exclusive=1.0),
                control_region=ControlRegion(*(float(value) for value in region_values)),
            ),
            gestures=GestureConfig(
                pinch_threshold=_number(gestures, "pinch_threshold", minimum=0.000001),
                pinch_confirmation_frames=_integer(gestures, "pinch_confirmation_frames", minimum=1),
                cooldown_seconds=_number(gestures, "cooldown_seconds", minimum=0.0),
                scroll_sensitivity=_number(gestures, "scroll_sensitivity", minimum=0.000001),
                fist_confirmation_frames=_integer(gestures, "fist_confirmation_frames", minimum=1),
            ),
        )
    except KeyError as error:
        raise ConfigurationError(f"Missing configuration value: {error.args[0]}") from error
    except (TypeError, ValueError) as error:
        if isinstance(error, ConfigurationError):
            raise
        raise ConfigurationError(f"Invalid configuration value: {error}") from error


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration section '{name}' must be an object.")
    return value


def _integer(section: dict[str, Any], name: str, minimum: int) -> int:
    value = section[name]
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ConfigurationError(f"{name} must be an integer of at least {minimum}.")
    return value


def _number(
    section: dict[str, Any],
    name: str,
    minimum: float,
    maximum_exclusive: float | None = None,
) -> float:
    value = section[name]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < minimum:
        raise ConfigurationError(f"{name} must be a number of at least {minimum}.")
    numeric = float(value)
    if maximum_exclusive is not None and numeric >= maximum_exclusive:
        raise ConfigurationError(f"{name} must be less than {maximum_exclusive}.")
    return numeric


def _probability(section: dict[str, Any], name: str) -> float:
    return _number(section, name, minimum=0.0, maximum_exclusive=1.000001)
