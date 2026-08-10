"""Phase 2 entry point: show a mirrored webcam preview with hand landmarks.

No gesture recognition or desktop-control actions are enabled in this phase.
Press Esc or Q while the preview has focus to quit.
"""

from __future__ import annotations

import argparse
import sys

import cv2

from vision.camera import CameraError, WebcamCamera
from vision.hand_tracker import HandTracker, HandTrackerError


WINDOW_TITLE = "Gesture Control - Hand Tracking"


def parse_args() -> argparse.Namespace:
    """Return command-line options for the webcam preview."""
    parser = argparse.ArgumentParser(description="Gesture Control camera preview")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index (default: 0)")
    parser.add_argument("--width", type=int, default=1280, help="Requested camera width")
    parser.add_argument("--height", type=int, default=720, help="Requested camera height")
    return parser.parse_args()


def run() -> int:
    """Open the webcam, annotate detected hands, and display frames until exit."""
    args = parse_args()

    try:
        with WebcamCamera(args.camera_index, args.width, args.height) as camera, HandTracker() as tracker:
            cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)

            while True:
                success, frame = camera.read()
                if not success:
                    print("Camera frame could not be read. Closing safely.", file=sys.stderr)
                    return 1

                # A mirrored image behaves like looking in a mirror and makes later cursor
                # control intuitive. Landmarks are extracted from this same orientation.
                frame = cv2.flip(frame, 1)
                hands = tracker.process(frame)
                tracker.draw(frame)
                cv2.putText(
                    frame,
                    f"Hands detected: {len(hands)} | Phase 2: tracking only",
                    (12, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                cv2.imshow(WINDOW_TITLE, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):  # Esc or Q
                    return 0

                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    return 0
    except (CameraError, HandTrackerError) as error:
        print(f"Startup error: {error}", file=sys.stderr)
        return 1
    except cv2.error as error:
        print(f"OpenCV error: {error}", file=sys.stderr)
        return 1
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
