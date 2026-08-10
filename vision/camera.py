"""Webcam lifecycle management, independent of gesture processing."""

from __future__ import annotations

from typing import Any

import cv2


class CameraError(RuntimeError):
    """Raised when the webcam cannot be opened or used."""


class WebcamCamera:
    """Own an OpenCV webcam capture and release it reliably.

    This class deliberately has no knowledge of hand tracking or gestures.
    """

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720) -> None:
        self.index = index
        self.width = width
        self.height = height
        self._capture: Any | None = None

    def open(self) -> None:
        """Open the selected camera, raising a clear error if unavailable."""
        if self.is_open:
            return

        # DirectShow reduces startup delay on Windows. Other platforms use the default backend.
        backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.index, backend)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Unable to open camera index {self.index}.")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._capture = capture

    @property
    def is_open(self) -> bool:
        """Whether the underlying OpenCV capture is ready to read frames."""
        return self._capture is not None and self._capture.isOpened()

    def read(self) -> tuple[bool, Any | None]:
        """Read and return the next camera frame.

        A failed read returns ``(False, None)`` so the app can stop safely.
        """
        if not self.is_open or self._capture is None:
            raise CameraError("Camera is not open.")
        return self._capture.read()

    def release(self) -> None:
        """Release the webcam; safe to call more than once."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "WebcamCamera":
        self.open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.release()
