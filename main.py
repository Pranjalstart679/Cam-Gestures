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
from control.cursor import ControlRegion, CursorMapper, ExponentialSmoother
from control.mouse import MouseControlError, MouseController


WINDOW_TITLE = "Gesture Control - Hand Tracking"


def parse_args() -> argparse.Namespace:
    """Return command-line options for the webcam preview."""
    parser = argparse.ArgumentParser(description="Gesture Control camera preview")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index (default: 0)")
    parser.add_argument("--width", type=int, default=1280, help="Requested camera width")
    parser.add_argument("--height", type=int, default=720, help="Requested camera height")
    parser.add_argument(
        "--enable-cursor",
        action="store_true",
        help="Opt in to index-finger cursor movement (no clicking is implemented).",
    )
    parser.add_argument(
        "--cursor-smoothing",
        type=float,
        default=0.70,
        help="EMA retention from 0 (none) to below 1 (default: 0.70).",
    )
    parser.add_argument(
        "--control-region",
        type=float,
        nargs=4,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        default=(0.20, 0.20, 0.80, 0.80),
        help="Normalized camera region that maps to the entire screen.",
    )
    return parser.parse_args()


def run() -> int:
    """Open the webcam, annotate detected hands, and display frames until exit."""
    args = parse_args()

    try:
        region = ControlRegion(*args.control_region)
        smoother = ExponentialSmoother(args.cursor_smoothing)
        with WebcamCamera(args.camera_index, args.width, args.height) as camera, HandTracker() as tracker:
            mouse = MouseController() if args.enable_cursor else None
            cursor_mapper = None
            if mouse is not None:
                screen_width, screen_height = mouse.screen_size()
                cursor_mapper = CursorMapper(screen_width, screen_height, region)

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

                frame_height, frame_width = frame.shape[:2]
                cv2.rectangle(
                    frame,
                    (round(region.left * frame_width), round(region.top * frame_height)),
                    (round(region.right * frame_width), round(region.bottom * frame_height)),
                    (255, 180, 0),
                    2,
                )

                cursor_label = "Cursor: preview only"
                if hands:
                    fingertip = hands[0].landmarks[8]  # MediaPipe index fingertip landmark.
                    cv2.circle(
                        frame,
                        (round(fingertip.x * frame_width), round(fingertip.y * frame_height)),
                        8,
                        (0, 255, 255),
                        -1,
                    )
                    if cursor_mapper is not None and mouse is not None:
                        smoothed_point = smoother.update(cursor_mapper.map(fingertip.x, fingertip.y))
                        mouse.move(smoothed_point.x, smoothed_point.y)
                        cursor_label = f"Cursor: {smoothed_point.x}, {smoothed_point.y}"
                else:
                    smoother.reset()

                cv2.putText(
                    frame,
                    f"Hands: {len(hands)} | {cursor_label}",
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
    except (CameraError, HandTrackerError, MouseControlError, ValueError) as error:
        print(f"Startup error: {error}", file=sys.stderr)
        return 1
    except cv2.error as error:
        print(f"OpenCV error: {error}", file=sys.stderr)
        return 1
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
