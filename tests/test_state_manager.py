"""State-machine checks for drag confirmation, cooldown, and state transitions."""

from __future__ import annotations

import unittest

from core.constants import AppState
from core.state_manager import StateManager
from vision.gesture_detector import Gesture


class StateManagerTests(unittest.TestCase):
    def test_fist_starts_drag_only_after_confirmation_and_ends_on_release(self) -> None:
        manager = StateManager(fist_confirmation_frames=3)
        self.assertEqual(manager.update(Gesture.FIST, 1.0).current, AppState.ACTIVE)
        self.assertEqual(manager.update(Gesture.FIST, 1.1).current, AppState.ACTIVE)
        start = manager.update(Gesture.FIST, 1.2)
        self.assertTrue(start.start_drag)
        self.assertEqual(start.current, AppState.DRAGGING)

        end = manager.update(Gesture.OPEN_HAND, 1.3)
        self.assertTrue(end.end_drag)
        self.assertEqual(end.current, AppState.ACTIVE)

    def test_two_finger_and_cooldown_states(self) -> None:
        manager = StateManager(cooldown_seconds=0.2)
        self.assertEqual(manager.update(Gesture.TWO_FINGER, 1.0).current, AppState.SCROLLING)
        manager.begin_cooldown(1.0)
        self.assertEqual(manager.update(Gesture.FIST, 1.1).current, AppState.COOLDOWN)
        self.assertEqual(manager.update(Gesture.NONE, 1.3).current, AppState.IDLE)

    def test_force_idle_requests_drag_release(self) -> None:
        manager = StateManager(fist_confirmation_frames=1)
        manager.update(Gesture.FIST, 1.0)
        self.assertTrue(manager.force_idle().end_drag)


if __name__ == "__main__":
    unittest.main()
