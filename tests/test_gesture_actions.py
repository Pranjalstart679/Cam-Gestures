"""Pure gesture-classification, click-gating, and scroll-math tests."""

from __future__ import annotations

import unittest

from control.actions import PinchClickGate, ScrollAccumulator
from vision.gesture_detector import Gesture, GestureDetector
from vision.hand_tracker import NormalizedLandmark, TrackedHand


def make_hand(*, pinch: bool = False, extended: tuple[bool, bool, bool, bool] = (False, False, False, False)) -> TrackedHand:
    """Build a simplified but valid landmark hand for deterministic tests."""
    points = [NormalizedLandmark(0.5, 0.7, 0.0) for _ in range(21)]
    points[0] = NormalizedLandmark(0.5, 0.8, 0.0)  # wrist
    points[9] = NormalizedLandmark(0.5, 0.4, 0.0)  # middle MCP, palm-size reference
    points[8] = NormalizedLandmark(0.50, 0.3, 0.0)

    for tip, pip, is_extended in ((8, 6, extended[0]), (12, 10, extended[1]), (16, 14, extended[2]), (20, 18, extended[3])):
        points[pip] = NormalizedLandmark(points[tip].x, 0.5, 0.0)
        points[tip] = NormalizedLandmark(points[tip].x, 0.3 if is_extended else 0.7, 0.0)
    index_tip = points[8]
    points[4] = NormalizedLandmark(
        index_tip.x - 0.04 if pinch else 0.1,
        index_tip.y if pinch else 0.3,
        0.0,
    )
    return TrackedHand(tuple(points), "Right", 1.0)


class GestureDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = GestureDetector()

    def test_pinch_uses_relative_distance(self) -> None:
        self.assertEqual(self.detector.detect(make_hand(pinch=True)).gesture, Gesture.PINCH)

    def test_index_point_and_two_finger_are_distinct(self) -> None:
        self.assertEqual(self.detector.detect(make_hand(extended=(True, False, False, False))).gesture, Gesture.INDEX_POINT)
        self.assertEqual(self.detector.detect(make_hand(extended=(True, True, False, False))).gesture, Gesture.TWO_FINGER)


class ActionTimingTests(unittest.TestCase):
    def test_pinch_gate_clicks_once_until_release(self) -> None:
        gate = PinchClickGate(confirmation_frames=3, cooldown_seconds=0.2)
        self.assertFalse(gate.update(True, 1.0))
        self.assertFalse(gate.update(True, 1.01))
        self.assertTrue(gate.update(True, 1.02))
        self.assertFalse(gate.update(True, 2.0))
        self.assertFalse(gate.update(False, 2.01))
        self.assertFalse(gate.update(True, 2.02))
        self.assertFalse(gate.update(True, 2.03))
        self.assertTrue(gate.update(True, 2.04))

    def test_scroll_accumulator_uses_vertical_motion(self) -> None:
        scroll = ScrollAccumulator(sensitivity=1.0)
        self.assertEqual(scroll.update(0.50), 0)
        self.assertEqual(scroll.update(0.48), 2)
        self.assertEqual(scroll.update(0.51), -3)


if __name__ == "__main__":
    unittest.main()
