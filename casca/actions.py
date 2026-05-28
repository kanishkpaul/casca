from pydantic import BaseModel, Field
from typing import Literal

class BaseAction(BaseModel):
    reason: str = Field(description="Reason for taking this action.")

class ClickAction(BaseAction):
    action: Literal["click"]
    x: int
    y: int

class DoubleClickAction(BaseAction):
    action: Literal["double_click"]
    x: int
    y: int

class RightClickAction(BaseAction):
    action: Literal["right_click"]
    x: int
    y: int

class MoveMouseAction(BaseAction):
    action: Literal["move_mouse"]
    x: int
    y: int

class DragAction(BaseAction):
    action: Literal["drag"]
    x1: int
    y1: int
    x2: int
    y2: int
    duration: float = 0.3

class TypeAction(BaseAction):
    action: Literal["type"]
    text: str

class PressAction(BaseAction):
    action: Literal["press"]
    key: str

class HotkeyAction(BaseAction):
    action: Literal["hotkey"]
    keys: list[str]

class ScrollAction(BaseAction):
    action: Literal["scroll"]
    amount: int

class WaitAction(BaseAction):
    action: Literal["wait"]
    ms: int

class DoneAction(BaseAction):
    action: Literal["done"]
    answer: str

class FailAction(BaseAction):
    action: Literal["fail"]
    reason: str

ActionType = (
    ClickAction
    | DoubleClickAction
    | RightClickAction
    | MoveMouseAction
    | DragAction
    | TypeAction
    | PressAction
    | HotkeyAction
    | ScrollAction
    | WaitAction
    | DoneAction
    | FailAction
)
