import pytest
from pydantic import TypeAdapter, ValidationError

from casca.actions import ActionType

BAD = [
    {"action": "wait", "ms": -500},
    {"action": "wait", "ms": 97_200_000},
    {"action": "click", "x": -5, "y": 10},
    {"action": "drag", "x1": 0, "y1": 0, "x2": 5, "y2": 5, "duration": -1},
    {"action": "hotkey", "keys": []},
    {"action": "type", "text": ""},
]


@pytest.mark.parametrize("data", BAD)
def test_out_of_range_actions_are_rejected(data):
    with pytest.raises(ValidationError):
        TypeAdapter(ActionType).validate_python({**data, "reason": "r"})
