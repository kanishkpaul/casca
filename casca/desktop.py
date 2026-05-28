import pyautogui
from casca.actions import (
    BaseAction, ClickAction, DoubleClickAction, RightClickAction,
    MoveMouseAction, DragAction, TypeAction, PressAction, HotkeyAction,
    ScrollAction, WaitAction, DoneAction, FailAction
)
import time

class DesktopController:
    def __init__(self, screen_width: int, screen_height: int, pause: float = 0.05):
        self.screen_width = screen_width
        self.screen_height = screen_height
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = pause

    def _bound_coords(self, x: int, y: int) -> tuple[int, int]:
        bx = max(0, min(x, self.screen_width - 1))
        by = max(0, min(y, self.screen_height - 1))
        return bx, by

    def move_mouse(self, x: int, y: int, duration: float = 0.1) -> None:
        bx, by = self._bound_coords(x, y)
        pyautogui.moveTo(bx, by, duration=duration)

    def click(self, x: int, y: int) -> None:
        bx, by = self._bound_coords(x, y)
        pyautogui.click(bx, by)

    def double_click(self, x: int, y: int) -> None:
        bx, by = self._bound_coords(x, y)
        pyautogui.doubleClick(bx, by)

    def right_click(self, x: int, y: int) -> None:
        bx, by = self._bound_coords(x, y)
        pyautogui.rightClick(bx, by)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        bx1, by1 = self._bound_coords(x1, y1)
        bx2, by2 = self._bound_coords(x2, y2)
        pyautogui.moveTo(bx1, by1)
        pyautogui.dragTo(bx2, by2, duration=duration)

    def type_text(self, text: str, interval: float = 0.01) -> None:
        pyautogui.typewrite(text, interval=interval)

    def press(self, key: str) -> None:
        pyautogui.press(key)

    def hotkey(self, keys: list[str]) -> None:
        pyautogui.hotkey(*keys)

    def scroll(self, amount: int) -> None:
        pyautogui.scroll(amount)

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
        elif isinstance(action, DoneAction):
            pass # Handled in loop
        elif isinstance(action, FailAction):
            pass # Handled in loop
        else:
            return {"status": "error", "error": f"Unknown action: {type(action).__name__}"}
            
        return {"status": "success"}
