"""MediaPipe hand-landmark tracking, independent of gesture interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp
import numpy as np


class HandTrackerError(RuntimeError):
    """Raised when the MediaPipe hand tracker cannot be initialized."""


@dataclass(frozen=True, slots=True)
class NormalizedLandmark:
    """A hand landmark expressed in MediaPipe's normalized coordinate space."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class TrackedHand:
    """One detected hand and its 21 normalized landmarks."""

    landmarks: tuple[NormalizedLandmark, ...]
    handedness: str
    confidence: float


class HandTracker:
    """Detect up to ``max_num_hands`` hands and expose normalized landmarks.

    The returned values remain in normalized coordinates so later gesture logic is
    independent of the webcam's pixel resolution. This class performs no gesture
    recognition and triggers no desktop actions.
    """

    def __init__(
        self,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.65,
        min_tracking_confidence: float = 0.60,
    ) -> None:
        self._hands: Any | None = None
        if not hasattr(mp, "solutions"):
            version = getattr(mp, "__version__", "unknown")
            raise HandTrackerError(
                "This project requires MediaPipe 0.10.14. "
                f"Found incompatible MediaPipe {version}. Run: "
                ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            )
        self._drawing_utils = mp.solutions.drawing_utils
        self._hand_connections = mp.solutions.hands.HAND_CONNECTIONS

        try:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                model_complexity=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        except Exception as error:  # MediaPipe raises backend-specific exceptions.
            raise HandTrackerError("Unable to initialize MediaPipe hand tracking.") from error

        self._last_results: Any | None = None

    def process(self, frame_bgr: np.ndarray) -> tuple[TrackedHand, ...]:
        """Detect hands in a BGR OpenCV frame and return normalized landmarks."""
        if self._hands is None:
            raise HandTrackerError("Hand tracker has been closed.")
        if frame_bgr is None or frame_bgr.size == 0:
            return ()

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        self._last_results = self._hands.process(frame_rgb)
        frame_rgb.flags.writeable = True

        multi_landmarks = self._last_results.multi_hand_landmarks or []
        multi_handedness = self._last_results.multi_handedness or []
        tracked_hands: list[TrackedHand] = []

        for index, hand_landmarks in enumerate(multi_landmarks):
            classification = multi_handedness[index].classification[0] if index < len(multi_handedness) else None
            tracked_hands.append(
                TrackedHand(
                    landmarks=tuple(
                        NormalizedLandmark(point.x, point.y, point.z)
                        for point in hand_landmarks.landmark
                    ),
                    handedness=classification.label if classification is not None else "Unknown",
                    confidence=classification.score if classification is not None else 0.0,
                )
            )
        return tuple(tracked_hands)

    def draw(self, frame_bgr: np.ndarray) -> None:
        """Draw the most recently detected landmarks onto a frame for debugging."""
        if self._last_results is None or not self._last_results.multi_hand_landmarks:
            return
        for hand_landmarks in self._last_results.multi_hand_landmarks:
            self._drawing_utils.draw_landmarks(frame_bgr, hand_landmarks, self._hand_connections)

    def close(self) -> None:
        """Release MediaPipe resources; safe to call more than once."""
        if self._hands is not None:
            self._hands.close()
            self._hands = None
        self._last_results = None

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
