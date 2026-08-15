"""Session lifecycle and voice-phrase matching tests."""

from __future__ import annotations

import unittest

from core.constants import SessionEvent, SessionMode
from core.session import SessionController
from voice.commands import PhraseMatcher, normalize_phrase


class SessionControllerTests(unittest.TestCase):
    def test_listen_first_activates_and_returns_to_listening(self) -> None:
        session = SessionController(listen_first=True)
        self.assertEqual(session.mode, SessionMode.LISTENING)
        session.handle(SessionEvent.ACTIVATE)
        self.assertEqual(session.mode, SessionMode.ACTIVE)
        self.assertTrue(session.running)
        session.handle(SessionEvent.DEACTIVATE)
        self.assertEqual(session.mode, SessionMode.LISTENING)
        session.handle(SessionEvent.QUIT)
        self.assertFalse(session.running)

    def test_immediate_camera_quit_on_deactivate(self) -> None:
        session = SessionController(listen_first=False)
        self.assertEqual(session.mode, SessionMode.ACTIVE)
        session.handle(SessionEvent.ACTIVATE)
        self.assertEqual(session.mode, SessionMode.ACTIVE)
        session.handle(SessionEvent.DEACTIVATE)
        self.assertFalse(session.running)


class PhraseMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = PhraseMatcher("activate", "stop", "quit")

    def test_wake_stop_and_quit(self) -> None:
        self.assertEqual(self.matcher.match("please activate now"), SessionEvent.ACTIVATE)
        self.assertEqual(self.matcher.match("STOP"), SessionEvent.DEACTIVATE)
        self.assertEqual(self.matcher.match("you should quit"), SessionEvent.QUIT)
        self.assertEqual(self.matcher.match("hello there"), SessionEvent.NONE)

    def test_quit_outranks_other_phrases(self) -> None:
        self.assertEqual(self.matcher.match("activate then quit"), SessionEvent.QUIT)

    def test_substring_is_not_enough(self) -> None:
        self.assertEqual(self.matcher.match("unstoppable"), SessionEvent.NONE)
        self.assertEqual(normalize_phrase("  Activate!  "), "activate")

    def test_phrases_must_be_distinct(self) -> None:
        with self.assertRaises(ValueError):
            PhraseMatcher("stop", "stop", "quit")


if __name__ == "__main__":
    unittest.main()
