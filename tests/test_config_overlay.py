"""Tests for local JSON configuration and debug-overlay timing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.config import ConfigurationError, load_config
from ui.overlay import DebugInfo, DebugOverlay


class ConfigurationTests(unittest.TestCase):
    def test_default_configuration_loads(self) -> None:
        config = load_config(Path("config/gestures.json"))
        self.assertEqual(config.camera.index, 0)
        self.assertEqual(config.cursor.control_region.left, 0.2)
        self.assertEqual(config.gestures.pinch_confirmation_frames, 3)
        self.assertFalse(config.voice.enabled)
        self.assertEqual(config.voice.wake_phrase, "activate")

    def test_invalid_region_is_rejected(self) -> None:
        invalid = {
            "camera": {"index": 0, "width": 640, "height": 480},
            "hand_tracking": {"max_num_hands": 1, "min_detection_confidence": 0.6, "min_tracking_confidence": 0.6},
            "cursor": {"smoothing": 0.7, "control_region": [0.8, 0.2, 0.2, 0.8]},
            "gestures": {
                "pinch_threshold": 0.38,
                "pinch_confirmation_frames": 3,
                "cooldown_seconds": 0.2,
                "scroll_sensitivity": 1.0,
                "fist_confirmation_frames": 3,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "invalid.json"
            config_path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(config_path)

    def test_missing_voice_section_uses_defaults(self) -> None:
        payload = {
            "camera": {"index": 0, "width": 640, "height": 480},
            "hand_tracking": {"max_num_hands": 1, "min_detection_confidence": 0.6, "min_tracking_confidence": 0.6},
            "cursor": {"smoothing": 0.7, "control_region": [0.2, 0.2, 0.8, 0.8]},
            "gestures": {
                "pinch_threshold": 0.38,
                "pinch_confirmation_frames": 3,
                "cooldown_seconds": 0.2,
                "scroll_sensitivity": 1.0,
                "fist_confirmation_frames": 3,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "no-voice.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_config(config_path)
            self.assertFalse(config.voice.enabled)
            self.assertEqual(config.voice.wake_phrase, "activate")


class DebugOverlayTests(unittest.TestCase):
    def test_fps_and_draw(self) -> None:
        overlay = DebugOverlay()
        self.assertEqual(overlay.update_fps(1.0), 0.0)
        self.assertAlmostEqual(overlay.update_fps(1.1), 10.0)
        frame = np.zeros((200, 600, 3), dtype=np.uint8)
        overlay.draw(
            frame,
            DebugInfo(True, "INDEX_POINT", "ACTIVE", (0.5, 0.4), 0.42, "Cursor: preview", "Actions: ready"),
        )
        self.assertTrue(frame.any())


if __name__ == "__main__":
    unittest.main()
