from pydantic import BaseModel, Field
from typing import Annotated, Literal

Coord = Annotated[int, Field(ge=0)]

class BaseAction(BaseModel):
    reason: str = Field(description="Reason for taking this action.")

class ClickAction(BaseAction):
    action: Literal["click"]
    x: Coord
    y: Coord

class DoubleClickAction(BaseAction):
    action: Literal["double_click"]
    x: Coord
    y: Coord

class RightClickAction(BaseAction):
    action: Literal["right_click"]
    x: Coord
    y: Coord

class MoveMouseAction(BaseAction):
    action: Literal["move_mouse"]
    x: Coord
    y: Coord

class DragAction(BaseAction):
    action: Literal["drag"]
    x1: Coord
    y1: Coord
    x2: Coord
    y2: Coord
    duration: float = Field(0.3, gt=0, le=5)

class TypeAction(BaseAction):
    action: Literal["type"]
    text: str = Field(min_length=1)

class PressAction(BaseAction):
    action: Literal["press"]
    key: str

class HotkeyAction(BaseAction):
    action: Literal["hotkey"]
    keys: list[str] = Field(min_length=1)

class ScrollAction(BaseAction):
    action: Literal["scroll"]
    amount: int

class WaitAction(BaseAction):
    action: Literal["wait"]
    ms: int = Field(ge=0, le=10_000)

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
