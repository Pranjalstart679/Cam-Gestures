"""Phase 5 entry point: webcam gesture control with explicit action opt-ins.

No gesture recognition or desktop-control actions are enabled in this phase.
Press Esc or Q while the preview has focus to quit.
"""

from __future__ import annotations

import argparse
import sys
from time import monotonic

import cv2

from control.actions import GestureActionRouter
from control.cursor import ControlRegion, CursorMapper, ExponentialSmoother
from control.mouse import MouseControlError, MouseController
from vision.camera import CameraError, WebcamCamera
from vision.gesture_detector import Gesture, GestureDetector
from vision.hand_tracker import HandTracker, HandTrackerError


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
        help="Opt in to index-finger cursor movement.",
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
    parser.add_argument(
        "--enable-gesture-actions",
        action="store_true",
        help="Opt in to pinch clicking and two-finger scrolling.",
    )
    parser.add_argument("--pinch-threshold", type=float, default=0.38, help="Relative thumb/index pinch threshold.")
    parser.add_argument("--pinch-frames", type=int, default=3, help="Frames required to confirm a pinch.")
    parser.add_argument("--click-cooldown", type=float, default=0.20, help="Minimum seconds between pinch clicks.")
    parser.add_argument("--scroll-sensitivity", type=float, default=1.0, help="Two-finger scroll sensitivity.")
    return parser.parse_args()


def run() -> int:
    """Open the webcam, annotate detected hands, and display frames until exit."""
    args = parse_args()

    try:
        region = ControlRegion(*args.control_region)
        smoother = ExponentialSmoother(args.cursor_smoothing)
        detector = GestureDetector(args.pinch_threshold)
        with WebcamCamera(args.camera_index, args.width, args.height) as camera, HandTracker() as tracker:
            mouse = MouseController() if args.enable_cursor or args.enable_gesture_actions else None
            cursor_mapper = None
            if mouse is not None:
                screen_width, screen_height = mouse.screen_size()
                cursor_mapper = CursorMapper(screen_width, screen_height, region)
            action_router = (
                GestureActionRouter(
                    mouse,
                    pinch_confirmation_frames=args.pinch_frames,
                    click_cooldown_seconds=args.click_cooldown,
                    scroll_sensitivity=args.scroll_sensitivity,
                )
                if args.enable_gesture_actions and mouse is not None
                else None
            )

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

                observation = detector.detect(hands[0]) if hands else None
                gesture_name = observation.gesture.name if observation is not None else Gesture.NONE.name
                action_result = action_router.update(observation, monotonic()) if action_router is not None else None

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
                    if (
                        observation is not None
                        and observation.gesture is Gesture.INDEX_POINT
                        and args.enable_cursor
                        and cursor_mapper is not None
                        and mouse is not None
                    ):
                        smoothed_point = smoother.update(cursor_mapper.map(fingertip.x, fingertip.y))
                        mouse.move(smoothed_point.x, smoothed_point.y)
                        cursor_label = f"Cursor: {smoothed_point.x}, {smoothed_point.y}"
                else:
                    smoother.reset()

                action_label = "Actions: disabled"
                if action_result is not None:
                    if action_result.clicked:
                        action_label = "Action: left click"
                    elif action_result.scroll_amount:
                        action_label = f"Action: scroll {action_result.scroll_amount:+d}"
                    else:
                        action_label = "Actions: ready"

                cv2.putText(
                    frame,
                    f"Hands: {len(hands)} | Gesture: {gesture_name} | {cursor_label}",
                    (12, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    action_label,
                    (12, 58),
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
