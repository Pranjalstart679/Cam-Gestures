"""Phase 5 entry point: webcam gesture control with explicit action opt-ins.

No gesture recognition or desktop-control actions are enabled in this phase.
Press Esc or Q while the preview has focus to quit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import monotonic

import cv2

from control.actions import GestureActionRouter
from control.cursor import ControlRegion, CursorMapper, ExponentialSmoother
from control.mouse import MouseControlError, MouseController
from core.config import ConfigurationError, load_config
from core.constants import AppState
from core.state_manager import StateManager
from ui.overlay import DebugInfo, DebugOverlay
from vision.camera import CameraError, WebcamCamera
from vision.gesture_detector import Gesture, GestureDetector
from vision.hand_tracker import HandTracker, HandTrackerError


WINDOW_TITLE = "Gesture Control - Hand Tracking"


def parse_args() -> argparse.Namespace:
    """Return command-line options for the webcam preview."""
    parser = argparse.ArgumentParser(description="Gesture Control camera preview")
    parser.add_argument("--config", type=Path, default=Path("config/gestures.json"), help="Path to local JSON settings.")
    parser.add_argument("--camera-index", type=int, default=None, help="Override webcam index from configuration.")
    parser.add_argument("--width", type=int, default=None, help="Override camera width from configuration.")
    parser.add_argument("--height", type=int, default=None, help="Override camera height from configuration.")
    parser.add_argument(
        "--enable-cursor",
        action="store_true",
        help="Opt in to index-finger cursor movement.",
    )
    parser.add_argument(
        "--cursor-smoothing",
        type=float,
        default=None,
        help="Override EMA retention from configuration (0 to below 1).",
    )
    parser.add_argument(
        "--control-region",
        type=float,
        nargs=4,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        default=None,
        help="Override normalized camera region that maps to the entire screen.",
    )
    parser.add_argument(
        "--enable-gesture-actions",
        action="store_true",
        help="Opt in to pinch clicking and two-finger scrolling.",
    )
    parser.add_argument("--pinch-threshold", type=float, default=None, help="Override relative thumb/index pinch threshold.")
    parser.add_argument("--pinch-frames", type=int, default=None, help="Override frames required to confirm a pinch.")
    parser.add_argument("--click-cooldown", type=float, default=None, help="Override minimum seconds between pinch clicks.")
    parser.add_argument("--scroll-sensitivity", type=float, default=None, help="Override two-finger scroll sensitivity.")
    parser.add_argument("--fist-frames", type=int, default=None, help="Override frames required to confirm a fist drag.")
    return parser.parse_args()


def run() -> int:
    """Open the webcam, annotate detected hands, and display frames until exit."""
    args = parse_args()
    mouse: MouseController | None = None

    try:
        config = load_config(args.config)
        camera_index = config.camera.index if args.camera_index is None else args.camera_index
        camera_width = config.camera.width if args.width is None else args.width
        camera_height = config.camera.height if args.height is None else args.height
        region = config.cursor.control_region if args.control_region is None else ControlRegion(*args.control_region)
        smoothing = config.cursor.smoothing if args.cursor_smoothing is None else args.cursor_smoothing
        pinch_threshold = config.gestures.pinch_threshold if args.pinch_threshold is None else args.pinch_threshold
        pinch_frames = config.gestures.pinch_confirmation_frames if args.pinch_frames is None else args.pinch_frames
        click_cooldown = config.gestures.cooldown_seconds if args.click_cooldown is None else args.click_cooldown
        scroll_sensitivity = config.gestures.scroll_sensitivity if args.scroll_sensitivity is None else args.scroll_sensitivity
        fist_frames = config.gestures.fist_confirmation_frames if args.fist_frames is None else args.fist_frames

        smoother = ExponentialSmoother(smoothing)
        detector = GestureDetector(pinch_threshold)
        state_manager = StateManager(fist_frames, click_cooldown)
        overlay = DebugOverlay()
        with WebcamCamera(camera_index, camera_width, camera_height) as camera, HandTracker(
            max_num_hands=config.hand_tracking.max_num_hands,
            min_detection_confidence=config.hand_tracking.min_detection_confidence,
            min_tracking_confidence=config.hand_tracking.min_tracking_confidence,
        ) as tracker:
            mouse = MouseController() if args.enable_cursor or args.enable_gesture_actions else None
            cursor_mapper = None
            if mouse is not None:
                screen_width, screen_height = mouse.screen_size()
                cursor_mapper = CursorMapper(screen_width, screen_height, region)
            action_router = (
                GestureActionRouter(
                    mouse,
                    pinch_confirmation_frames=pinch_frames,
                    click_cooldown_seconds=click_cooldown,
                    scroll_sensitivity=scroll_sensitivity,
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
                now = monotonic()
                transition = state_manager.update(
                    observation.gesture if observation is not None else Gesture.NONE,
                    now,
                )
                if transition.start_drag and mouse is not None and args.enable_gesture_actions:
                    mouse.mouse_down()
                if transition.end_drag and mouse is not None:
                    mouse.mouse_up()

                action_observation = observation if state_manager.state is not AppState.DRAGGING else None
                action_result = action_router.update(action_observation, now) if action_router is not None else None
                if action_result is not None and action_result.clicked:
                    state_manager.begin_cooldown(now)

                cursor_label = "Cursor: preview only"
                fingertip_coordinates: tuple[float, float] | None = None
                if hands:
                    fingertip = hands[0].landmarks[8]  # MediaPipe index fingertip landmark.
                    fingertip_coordinates = (fingertip.x, fingertip.y)
                    cv2.circle(
                        frame,
                        (round(fingertip.x * frame_width), round(fingertip.y * frame_height)),
                        8,
                        (0, 255, 255),
                        -1,
                    )
                    should_move_cursor = observation is not None and (
                        (observation.gesture is Gesture.INDEX_POINT and args.enable_cursor)
                        or (
                            observation.gesture is Gesture.FIST
                            and state_manager.state is AppState.DRAGGING
                            and args.enable_gesture_actions
                        )
                    )
                    if should_move_cursor and cursor_mapper is not None and mouse is not None:
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

                overlay.draw(
                    frame,
                    DebugInfo(
                        hand_detected=bool(hands),
                        gesture=gesture_name,
                        state=state_manager.state.name,
                        fingertip=fingertip_coordinates,
                        pinch_ratio=observation.pinch_ratio if observation is not None else None,
                        cursor_label=cursor_label,
                        action_label=action_label,
                    ),
                )

                cv2.imshow(WINDOW_TITLE, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):  # Esc or Q
                    return 0

                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    return 0
    except (CameraError, ConfigurationError, HandTrackerError, MouseControlError, ValueError) as error:
        print(f"Startup error: {error}", file=sys.stderr)
        return 1
    except cv2.error as error:
        print(f"OpenCV error: {error}", file=sys.stderr)
        return 1
    finally:
        if mouse is not None:
            mouse.release_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
