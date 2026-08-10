"""Rule-based conversion of normalized hand landmarks into semantic gestures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import sqrt

from vision.hand_tracker import NormalizedLandmark, TrackedHand


class Gesture(Enum):
    """Semantic hand shapes recognized by the first gesture-control version."""

    NONE = auto()
    INDEX_POINT = auto()
    PINCH = auto()
    TWO_FINGER = auto()
    FIST = auto()
    OPEN_HAND = auto()


@dataclass(frozen=True, slots=True)
class GestureObservation:
    """A gesture classification plus values needed by the action layer."""

    gesture: Gesture
    index_tip: NormalizedLandmark
    pinch_ratio: float
    scroll_anchor_y: float


class GestureDetector:
    """Classify one tracked hand using relative distances and finger extension."""

    _THUMB_TIP = 4
    _INDEX_TIP = 8
    _INDEX_PIP = 6
    _MIDDLE_TIP = 12
    _MIDDLE_PIP = 10
    _MIDDLE_MCP = 9
    _RING_TIP = 16
    _RING_PIP = 14
    _PINKY_TIP = 20
    _PINKY_PIP = 18
    _WRIST = 0

    def __init__(self, pinch_threshold: float = 0.38) -> None:
        if pinch_threshold <= 0:
            raise ValueError("Pinch threshold must be positive.")
        self._pinch_threshold = pinch_threshold

    def detect(self, hand: TrackedHand) -> GestureObservation:
        """Return a rule-based classification for a single hand."""
        landmarks = hand.landmarks
        if len(landmarks) != 21:
            raise ValueError("A MediaPipe hand must contain exactly 21 landmarks.")

        index_tip = landmarks[self._INDEX_TIP]
        pinch_ratio = self._distance(landmarks[self._THUMB_TIP], index_tip) / max(
            self._distance(landmarks[self._WRIST], landmarks[self._MIDDLE_MCP]), 1e-6
        )
        observation = GestureObservation(
            gesture=Gesture.NONE,
            index_tip=index_tip,
            pinch_ratio=pinch_ratio,
            scroll_anchor_y=(index_tip.y + landmarks[self._MIDDLE_TIP].y) / 2,
        )

        if pinch_ratio <= self._pinch_threshold:
            return self._with_gesture(observation, Gesture.PINCH)

        index_extended = self._is_extended(landmarks, self._INDEX_TIP, self._INDEX_PIP)
        middle_extended = self._is_extended(landmarks, self._MIDDLE_TIP, self._MIDDLE_PIP)
        ring_extended = self._is_extended(landmarks, self._RING_TIP, self._RING_PIP)
        pinky_extended = self._is_extended(landmarks, self._PINKY_TIP, self._PINKY_PIP)

        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return self._with_gesture(observation, Gesture.TWO_FINGER)
        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return self._with_gesture(observation, Gesture.INDEX_POINT)
        if not any((index_extended, middle_extended, ring_extended, pinky_extended)):
            return self._with_gesture(observation, Gesture.FIST)
        if all((index_extended, middle_extended, ring_extended, pinky_extended)):
            return self._with_gesture(observation, Gesture.OPEN_HAND)
        return observation

    @staticmethod
    def _with_gesture(observation: GestureObservation, gesture: Gesture) -> GestureObservation:
        return GestureObservation(
            gesture=gesture,
            index_tip=observation.index_tip,
            pinch_ratio=observation.pinch_ratio,
            scroll_anchor_y=observation.scroll_anchor_y,
        )

    @staticmethod
    def _is_extended(landmarks: tuple[NormalizedLandmark, ...], tip_index: int, pip_index: int) -> bool:
        """A non-thumb finger is extended when its tip is above its PIP joint."""
        return landmarks[tip_index].y < landmarks[pip_index].y

    @staticmethod
    def _distance(first: NormalizedLandmark, second: NormalizedLandmark) -> float:
        return sqrt(
            (first.x - second.x) ** 2 + (first.y - second.y) ** 2 + (first.z - second.z) ** 2
        )
