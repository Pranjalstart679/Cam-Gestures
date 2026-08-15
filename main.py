"""Webcam gesture control with optional listen-first voice activation.

Preview is harmless until --enable-cursor, --enable-gesture-actions, or --hands-free.
Press Esc or Q while the preview has focus to deactivate or quit.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import cv2
import numpy as np

from control.actions import GestureActionRouter
from control.cursor import ControlRegion, CursorMapper, ExponentialSmoother
from control.mouse import MouseControlError, MouseController
from core.config import AppConfig, ConfigurationError, load_config
from core.constants import AppState, SessionEvent, SessionMode
from core.session import SessionController
from core.state_manager import StateManager
from ui.overlay import DebugInfo, DebugOverlay
from vision.camera import CameraError, WebcamCamera
from vision.gesture_detector import Gesture, GestureDetector
from vision.hand_tracker import HandTracker, HandTrackerError
from voice.commands import PhraseMatcher
from voice.listener import VoiceError, VoiceListener


WINDOW_TITLE = "Gesture Control"


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    config: AppConfig
    camera_index: int
    camera_width: int
    camera_height: int
    region: ControlRegion
    smoothing: float
    pinch_threshold: float
    pinch_frames: int
    click_cooldown: float
    scroll_sensitivity: float
    fist_frames: int
    enable_cursor: bool
    enable_gesture_actions: bool
    voice_enabled: bool
    wake_phrase: str
    stop_phrase: str
    quit_phrase: str
    voice_model_path: Path


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
        "--hands-free",
        action="store_true",
        help="Enable cursor movement and gesture actions together.",
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
        help="Opt in to pinch clicking, two-finger scrolling, and fist dragging.",
    )
    parser.add_argument("--pinch-threshold", type=float, default=None, help="Override relative thumb/index pinch threshold.")
    parser.add_argument("--pinch-frames", type=int, default=None, help="Override frames required to confirm a pinch.")
    parser.add_argument("--click-cooldown", type=float, default=None, help="Override minimum seconds between pinch clicks.")
    parser.add_argument("--scroll-sensitivity", type=float, default=None, help="Override two-finger scroll sensitivity.")
    parser.add_argument("--fist-frames", type=int, default=None, help="Override frames required to confirm a fist drag.")
    parser.add_argument("--enable-voice", action="store_true", help="Keep the camera off until the wake phrase or Space.")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice even if it is enabled in configuration.")
    parser.add_argument("--wake-phrase", type=str, default=None, help="Override the voice phrase that starts the camera.")
    parser.add_argument("--stop-phrase", type=str, default=None, help="Override the voice phrase that stops the camera.")
    return parser.parse_args()


def build_runtime(args: argparse.Namespace, config: AppConfig) -> RuntimeSettings:
    """Merge configuration file values with command-line overrides."""
    voice_enabled = config.voice.enabled
    if args.enable_voice:
        voice_enabled = True
    if args.no_voice:
        voice_enabled = False
    return RuntimeSettings(
        config=config,
        camera_index=config.camera.index if args.camera_index is None else args.camera_index,
        camera_width=config.camera.width if args.width is None else args.width,
        camera_height=config.camera.height if args.height is None else args.height,
        region=config.cursor.control_region if args.control_region is None else ControlRegion(*args.control_region),
        smoothing=config.cursor.smoothing if args.cursor_smoothing is None else args.cursor_smoothing,
        pinch_threshold=config.gestures.pinch_threshold if args.pinch_threshold is None else args.pinch_threshold,
        pinch_frames=config.gestures.pinch_confirmation_frames if args.pinch_frames is None else args.pinch_frames,
        click_cooldown=config.gestures.cooldown_seconds if args.click_cooldown is None else args.click_cooldown,
        scroll_sensitivity=config.gestures.scroll_sensitivity if args.scroll_sensitivity is None else args.scroll_sensitivity,
        fist_frames=config.gestures.fist_confirmation_frames if args.fist_frames is None else args.fist_frames,
        enable_cursor=bool(args.enable_cursor or args.hands_free),
        enable_gesture_actions=bool(args.enable_gesture_actions or args.hands_free),
        voice_enabled=voice_enabled,
        wake_phrase=config.voice.wake_phrase if args.wake_phrase is None else args.wake_phrase,
        stop_phrase=config.voice.stop_phrase if args.stop_phrase is None else args.stop_phrase,
        quit_phrase=config.voice.quit_phrase,
        voice_model_path=config.voice.model_path,
    )


def event_from_key(key: int, session: SessionController) -> SessionEvent:
    """Map a focused-window keypress onto a session event."""
    if key in (ord("q"), ord("Q")):
        return SessionEvent.QUIT
    if key == 27:  # Esc
        if session.listen_first and session.mode is SessionMode.ACTIVE:
            return SessionEvent.DEACTIVATE
        return SessionEvent.QUIT
    if key in (ord("s"), ord("S")) and session.mode is SessionMode.ACTIVE:
        return SessionEvent.DEACTIVATE
    if key in (32, 13) and session.mode is SessionMode.LISTENING:
        return SessionEvent.ACTIVATE
    return SessionEvent.NONE


def listening_frame(settings: RuntimeSettings, transcript: str) -> np.ndarray:
    """Render a camera-off waiting screen so keyboard shortcuts still work."""
    frame = np.zeros((360, 720, 3), dtype=np.uint8)
    lines = (
        "Listening — camera is off",
        f'Say "{settings.wake_phrase}" or press Space to start',
        f'Say "{settings.stop_phrase}" or Esc to pause after start',
        f'Say "{settings.quit_phrase}" or Q to exit',
        f"Heard: {transcript or '...'}",
    )
    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (24, 70 + 50 * index),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return frame


def run_active_session(
    settings: RuntimeSettings,
    session: SessionController,
    overlay: DebugOverlay,
    listener: VoiceListener | None,
) -> SessionEvent:
    """Open the webcam until the user deactivates or quits."""
    mouse: MouseController | None = None
    try:
        with WebcamCamera(settings.camera_index, settings.camera_width, settings.camera_height) as camera, HandTracker(
            max_num_hands=settings.config.hand_tracking.max_num_hands,
            min_detection_confidence=settings.config.hand_tracking.min_detection_confidence,
            min_tracking_confidence=settings.config.hand_tracking.min_tracking_confidence,
        ) as tracker:
            smoother = ExponentialSmoother(settings.smoothing)
            detector = GestureDetector(settings.pinch_threshold)
            state_manager = StateManager(settings.fist_frames, settings.click_cooldown)
            mouse = MouseController() if settings.enable_cursor or settings.enable_gesture_actions else None
            cursor_mapper = None
            if mouse is not None:
                screen_width, screen_height = mouse.screen_size()
                cursor_mapper = CursorMapper(screen_width, screen_height, settings.region)
            action_router = (
                GestureActionRouter(
                    mouse,
                    pinch_confirmation_frames=settings.pinch_frames,
                    click_cooldown_seconds=settings.click_cooldown,
                    scroll_sensitivity=settings.scroll_sensitivity,
                )
                if settings.enable_gesture_actions and mouse is not None
                else None
            )

            while session.running and session.mode is SessionMode.ACTIVE:
                success, frame = camera.read()
                if not success:
                    print("Camera frame could not be read. Closing safely.", file=sys.stderr)
                    return SessionEvent.QUIT

                frame = cv2.flip(frame, 1)
                hands = tracker.process(frame)
                tracker.draw(frame)

                frame_height, frame_width = frame.shape[:2]
                cv2.rectangle(
                    frame,
                    (round(settings.region.left * frame_width), round(settings.region.top * frame_height)),
                    (round(settings.region.right * frame_width), round(settings.region.bottom * frame_height)),
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
                if transition.start_drag and mouse is not None and settings.enable_gesture_actions:
                    mouse.mouse_down()
                if transition.end_drag and mouse is not None:
                    mouse.mouse_up()

                if not hands and state_manager.state is AppState.DRAGGING and mouse is not None:
                    mouse.mouse_up()
                    state_manager.force_idle()

                action_observation = observation if state_manager.state is not AppState.DRAGGING else None
                action_result = action_router.update(action_observation, now) if action_router is not None else None
                if action_result is not None and action_result.clicked:
                    state_manager.begin_cooldown(now)

                cursor_label = "Cursor: preview only"
                fingertip_coordinates: tuple[float, float] | None = None
                if hands:
                    fingertip = hands[0].landmarks[8]
                    fingertip_coordinates = (fingertip.x, fingertip.y)
                    cv2.circle(
                        frame,
                        (round(fingertip.x * frame_width), round(fingertip.y * frame_height)),
                        8,
                        (0, 255, 255),
                        -1,
                    )
                    should_move_cursor = observation is not None and (
                        (observation.gesture is Gesture.INDEX_POINT and settings.enable_cursor)
                        or (
                            observation.gesture is Gesture.FIST
                            and state_manager.state is AppState.DRAGGING
                            and settings.enable_gesture_actions
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

                voice_label = ""
                if listener is not None:
                    voice_label = f"Heard: {listener.last_transcript or '...'}"

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
                        session_label="Session: ACTIVE",
                        voice_label=voice_label,
                    ),
                )
                cv2.imshow(WINDOW_TITLE, frame)

                event = SessionEvent.NONE
                if listener is not None:
                    event = listener.poll()
                key = cv2.waitKey(1) & 0xFF
                if event is SessionEvent.NONE:
                    event = event_from_key(key, session)
                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    event = SessionEvent.QUIT
                if event is not SessionEvent.NONE:
                    return event
            return SessionEvent.NONE
    finally:
        if mouse is not None:
            mouse.release_all()


def run() -> int:
    """Load settings, optionally listen for a wake phrase, then run camera sessions."""
    args = parse_args()
    listener: VoiceListener | None = None
    try:
        settings = build_runtime(args, load_config(args.config))
        session = SessionController(listen_first=settings.voice_enabled)
        overlay = DebugOverlay()
        if settings.voice_enabled:
            matcher = PhraseMatcher(settings.wake_phrase, settings.stop_phrase, settings.quit_phrase)
            try:
                listener = VoiceListener(matcher, settings.voice_model_path)
                listener.start()
                print(
                    f'Voice ready. Say "{settings.wake_phrase}" or press Space to start the camera.',
                    flush=True,
                )
            except VoiceError as error:
                listener = None
                print(
                    f"Voice microphone unavailable ({error}). "
                    "Camera stays off until you press Space. Press Q to quit.",
                    file=sys.stderr,
                )

        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        while session.running:
            if session.mode is SessionMode.LISTENING:
                transcript = listener.last_transcript if listener is not None else ""
                cv2.imshow(WINDOW_TITLE, listening_frame(settings, transcript))
                event = listener.poll() if listener is not None else SessionEvent.NONE
                key = cv2.waitKey(30) & 0xFF
                if event is SessionEvent.NONE:
                    event = event_from_key(key, session)
                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    event = SessionEvent.QUIT
                session.handle(event)
                continue

            event = run_active_session(settings, session, overlay, listener)
            session.handle(event)
        return 0
    except (CameraError, ConfigurationError, HandTrackerError, MouseControlError, VoiceError, ValueError) as error:
        print(f"Startup error: {error}", file=sys.stderr)
        return 1
    except cv2.error as error:
        print(f"OpenCV error: {error}", file=sys.stderr)
        return 1
    finally:
        if listener is not None:
            listener.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(run())
