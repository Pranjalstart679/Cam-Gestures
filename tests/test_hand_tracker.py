"""Non-hardware checks for Phase 2 hand tracking."""

from __future__ import annotations

import unittest

import numpy as np

from vision.hand_tracker import HandTracker


class HandTrackerTests(unittest.TestCase):
    def test_blank_frame_has_no_detected_hands(self) -> None:
        """A valid frame without a hand should return an empty immutable result."""
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        with HandTracker() as tracker:
            self.assertEqual(tracker.process(frame), ())


if __name__ == "__main__":
    unittest.main()
