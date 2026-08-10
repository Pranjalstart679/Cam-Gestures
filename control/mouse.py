"""A small safety-conscious adapter around PyAutoGUI mouse operations."""

from __future__ import annotations

from typing import Any


class MouseControlError(RuntimeError):
    """Raised when a requested OS mouse operation cannot be completed."""


class MouseController:
    """Hide PyAutoGUI details from gesture and application code."""

    def __init__(self) -> None:
        try:
            import pyautogui
        except ImportError as error:
            raise MouseControlError("PyAutoGUI is not installed. Run pip install -r requirements.txt.") from error

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0
        self._pyautogui: Any = pyautogui

    def screen_size(self) -> tuple[int, int]:
        """Return the primary desktop size in pixels."""
        size = self._pyautogui.size()
        return size.width, size.height

    def move(self, x: int, y: int) -> None:
        """Move immediately to a bounded screen coordinate without clicking."""
        width, height = self.screen_size()
        bounded_x = min(max(x, 0), width - 1)
        bounded_y = min(max(y, 0), height - 1)
        try:
            self._pyautogui.moveTo(bounded_x, bounded_y, duration=0)
        except self._pyautogui.FailSafeException as error:
            raise MouseControlError("PyAutoGUI fail-safe triggered; move away from a screen corner and restart.") from error

    def click(self) -> None:
        """Perform one left click. Reserved for a later phase."""
        self._pyautogui.click()

    def right_click(self) -> None:
        """Perform one right click. Reserved for a later phase."""
        self._pyautogui.rightClick()

    def double_click(self) -> None:
        """Perform one double click. Reserved for a later phase."""
        self._pyautogui.doubleClick()

    def mouse_down(self) -> None:
        """Hold the primary mouse button. Reserved for a later phase."""
        self._pyautogui.mouseDown()

    def mouse_up(self) -> None:
        """Release the primary mouse button. Reserved for a later phase."""
        self._pyautogui.mouseUp()

    def scroll(self, amount: int) -> None:
        """Scroll vertically. Reserved for a later phase."""
        self._pyautogui.scroll(amount)
