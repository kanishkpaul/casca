from pydantic import BaseModel, Field
from typing import Annotated, Literal

Coord = Annotated[int, Field(ge=0)]

class BaseAction(BaseModel):
    reason: str = Field(description="Reason for taking this action.")
    previous: Literal["held", "not_held", "unclear"] | None = Field(
        None, description="Whether the previous action's expect is true on this screenshot.")

class ActAction(BaseAction):
    expect: str = Field(min_length=1, description="What the screen should show after this action.")

class ClickAction(ActAction):
    action: Literal["click"]
    x: Coord
    y: Coord

class DoubleClickAction(ActAction):
    action: Literal["double_click"]
    x: Coord
    y: Coord

class RightClickAction(ActAction):
    action: Literal["right_click"]
    x: Coord
    y: Coord

class MoveMouseAction(ActAction):
    action: Literal["move_mouse"]
    x: Coord
    y: Coord

class DragAction(ActAction):
    action: Literal["drag"]
    x1: Coord
    y1: Coord
    x2: Coord
    y2: Coord
    duration: float = Field(0.3, gt=0, le=5)

class TypeAction(ActAction):
    action: Literal["type"]
    text: str = Field(min_length=1)

class PressAction(ActAction):
    action: Literal["press"]
    key: str

class HotkeyAction(ActAction):
    action: Literal["hotkey"]
    keys: list[str] = Field(min_length=1)

class ScrollAction(ActAction):
    action: Literal["scroll"]
    amount: int = Field(ge=-20, le=20, description="Mouse-wheel notches; negative scrolls down.")

class WaitAction(BaseAction):
    action: Literal["wait"]
    ms: int = Field(ge=0, le=10_000)

class OpenAppAction(ActAction):
    action: Literal["open_app"]
    name: str = Field(min_length=1, description="Application name, e.g. TextEdit or Notepad.")

class DoneAction(BaseAction):
    action: Literal["done"]
    answer: str

class HandbackAction(BaseAction):
    action: Literal["handback"]

class FailAction(BaseAction):
    action: Literal["fail"]
    reason: str

ActionType = Annotated[
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
    | OpenAppAction
    | HandbackAction
    | DoneAction
    | FailAction,
    Field(discriminator="action"),
]
