import pyautogui
from casca import native
from casca.actions import (
    BaseAction, ClickAction, DoubleClickAction, RightClickAction,
    MoveMouseAction, DragAction, TypeAction, PressAction, HotkeyAction,
    ScrollAction, WaitAction, OpenAppAction, DoneAction, FailAction
)
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"

KEY_ALIASES = {"cmd": "command", "win": "winleft", "super": "winleft"}
# PyAutoGUI scrolls lines on macOS and wheel delta (120 per notch) on Windows.
SCROLL_UNIT = {"darwin": 3, "win32": 120}.get(sys.platform, 1)

if sys.platform != "darwin":
    KEY_ALIASES.update(command="ctrl", cmd="ctrl")


def valid_key(key: str) -> str:
    """PyAutoGUI ignores names it does not know, so an unknown key would be reported as pressed."""
    name = KEY_ALIASES.get(key.lower(), key.lower())
    if not pyautogui.isValidKey(name):
        raise ValueError(f"unknown key {key!r}")
    return name

class DesktopController:
    def __init__(self, screen_width: int, screen_height: int, pause: float = 0.05):
        self.screen_width = screen_width
        self.screen_height = screen_height
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = pause

    def move_mouse(self, x: int, y: int, duration: float = 0.1) -> None:
        if WINDOWS:
            return native.win_move(x, y)
        pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: int, y: int) -> None:
        if WINDOWS:
            return native.win_click(x, y)
        pyautogui.click(x, y)

    def double_click(self, x: int, y: int) -> None:
        if WINDOWS:
            return native.win_click(x, y, count=2)
        pyautogui.doubleClick(x, y)

    def right_click(self, x: int, y: int) -> None:
        if WINDOWS:
            return native.win_click(x, y, "right")
        pyautogui.rightClick(x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        if WINDOWS:
            return native.win_drag(x1, y1, x2, y2, duration)
        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=duration)

    def type_text(self, text: str, interval: float = 0.01) -> None:
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            native.type_unicode(text)

    def press(self, key: str) -> None:
        pyautogui.press(valid_key(key))

    def hotkey(self, keys: list[str]) -> None:
        pyautogui.hotkey(*map(valid_key, keys))

    def scroll(self, amount: int) -> None:
        pyautogui.scroll(amount * SCROLL_UNIT)

    def input_problem(self) -> str | None:
        """Why input would be dropped, with the fix, or None. macOS drops synthetic events silently."""
        if sys.platform == "darwin":
            import Quartz
            if not Quartz.CGPreflightPostEventAccess():
                return ("Accessibility is not granted to this terminal. Enable it in System Settings > "
                        "Privacy & Security > Accessibility, then restart the terminal.")
        return None

    def open_app(self, name: str) -> None:
        command = ["open", "-a", name] if sys.platform == "darwin" else ["cmd", "/c", "start", "", name]
        subprocess.run(command, check=True, capture_output=True, timeout=10)

    def wait(self, ms: int) -> None:
        time.sleep(ms / 1000.0)

    def execute_action(self, action: BaseAction) -> dict:
        if isinstance(action, ClickAction):
            self.click(action.x, action.y)
        elif isinstance(action, DoubleClickAction):
            self.double_click(action.x, action.y)
        elif isinstance(action, RightClickAction):
            self.right_click(action.x, action.y)
        elif isinstance(action, MoveMouseAction):
            self.move_mouse(action.x, action.y)
        elif isinstance(action, DragAction):
            self.drag(action.x1, action.y1, action.x2, action.y2, action.duration)
        elif isinstance(action, TypeAction):
            self.type_text(action.text)
        elif isinstance(action, PressAction):
            self.press(action.key)
        elif isinstance(action, HotkeyAction):
            self.hotkey(action.keys)
        elif isinstance(action, ScrollAction):
            self.scroll(action.amount)
        elif isinstance(action, WaitAction):
            self.wait(action.ms)
        elif isinstance(action, OpenAppAction):
            self.open_app(action.name)
        elif isinstance(action, DoneAction):
            pass # Handled in loop
        elif isinstance(action, FailAction):
            pass # Handled in loop
        else:
            return {"status": "error", "error": f"Unknown action: {type(action).__name__}"}
            
        return {"status": "success"}
