"""Pure math checks for Phase 3 cursor mapping and smoothing."""

from __future__ import annotations

import unittest

from control.cursor import ControlRegion, CursorMapper, ExponentialSmoother, ScreenPoint


class CursorMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = CursorMapper(1920, 1080, ControlRegion(0.2, 0.2, 0.8, 0.8))

    def test_region_corners_map_to_screen_corners(self) -> None:
        self.assertEqual(self.mapper.map(0.2, 0.2), ScreenPoint(0, 0))
        self.assertEqual(self.mapper.map(0.8, 0.8), ScreenPoint(1919, 1079))

    def test_points_outside_region_are_clamped(self) -> None:
        self.assertEqual(self.mapper.map(-2.0, 3.0), ScreenPoint(0, 1079))

    def test_smoother_uses_previous_value(self) -> None:
        smoother = ExponentialSmoother(retention=0.5)
        self.assertEqual(smoother.update(ScreenPoint(0, 0)), ScreenPoint(0, 0))
        self.assertEqual(smoother.update(ScreenPoint(100, 80)), ScreenPoint(50, 40))


if __name__ == "__main__":
    unittest.main()
