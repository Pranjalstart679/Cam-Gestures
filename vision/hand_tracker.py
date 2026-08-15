"""MediaPipe hand-landmark tracking, independent of gesture interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.vision import drawing_utils, hand_landmarker
from mediapipe.tasks.python.vision.core import vision_task_running_mode as running_mode

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "hand_landmarker.task"


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
        model_path: Path | str | None = None,
    ) -> None:
        resolved_model = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
        if not resolved_model.is_file():
            raise HandTrackerError(
                f"Hand landmarker model not found at {resolved_model}. "
                "Download hand_landmarker.task into the models/ directory. "
                "See README.md for setup instructions."
            )

        self._hand_connections = hand_landmarker.HandLandmarksConnections.HAND_CONNECTIONS
        options = hand_landmarker.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
            running_mode=running_mode.VisionTaskRunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        try:
            self._landmarker: Any | None = hand_landmarker.HandLandmarker.create_from_options(options)
        except Exception as error:  # MediaPipe raises backend-specific exceptions.
            raise HandTrackerError("Unable to initialize MediaPipe hand tracking.") from error

        self._last_results: hand_landmarker.HandLandmarkerResult | None = None
        self._frame_timestamp_ms = 0

    def process(self, frame_bgr: np.ndarray) -> tuple[TrackedHand, ...]:
        """Detect hands in a BGR OpenCV frame and return normalized landmarks."""
        if self._landmarker is None:
            raise HandTrackerError("Hand tracker has been closed.")
        if frame_bgr is None or frame_bgr.size == 0:
            return ()

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        self._frame_timestamp_ms += 33
        self._last_results = self._landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        if not self._last_results.hand_landmarks:
            return ()

        tracked_hands: list[TrackedHand] = []
        for index, landmarks in enumerate(self._last_results.hand_landmarks):
            classification = None
            if self._last_results.handedness and index < len(self._last_results.handedness):
                handedness = self._last_results.handedness[index]
                classification = handedness[0] if handedness else None

            tracked_hands.append(
                TrackedHand(
                    landmarks=tuple(
                        NormalizedLandmark(point.x, point.y, point.z)
                        for point in landmarks
                    ),
                    handedness=classification.category_name if classification is not None else "Unknown",
                    confidence=classification.score if classification is not None else 0.0,
                )
            )
        return tuple(tracked_hands)

    def draw(self, frame_bgr: np.ndarray) -> None:
        """Draw the most recently detected landmarks onto a frame for debugging."""
        if self._last_results is None or not self._last_results.hand_landmarks:
            return
        for landmarks in self._last_results.hand_landmarks:
            drawing_utils.draw_landmarks(
                frame_bgr,
                landmarks,
                self._hand_connections,
            )

    def close(self) -> None:
        """Release MediaPipe resources; safe to call more than once."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
        self._last_results = None

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
