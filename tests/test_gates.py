import pytest

from casca.actions import ClickAction, OpenAppAction, TypeAction
from casca.gates import check

CLICK = ClickAction(action="click", x=1, y=1, reason="r", expect="e")


def element(app="TextEdit", role="AXButton", name="OK", secure=False):
    return {"app": app, "role": role, "name": name, "secure": secure}


@pytest.mark.parametrize("target, apps, decision", [
    (element(), ["TextEdit"], "allow"),
    (element(app="Open and Save Panel Service (TextEdit)"), ["TextEdit"], "allow"),
    (element(app="Claude"), ["TextEdit"], "refuse"),
    (element(name="Send"), [], "confirm"),
    (element(role="AXTextField", name="Post code"), [], "allow"),
    (element(role=None), [], "confirm"),
    (None, [], "confirm"),
])
def test_click_gate_reads_the_target(target, apps, decision):
    assert check(CLICK, target, None, apps)[0] == decision


def test_typing_into_a_password_field_is_refused_even_with_no_scope():
    typing = TypeAction(action="type", text="hunter2", reason="r", expect="e")
    assert check(typing, None, element(secure=True), [])[0] == "refuse"


def test_open_app_outside_scope_is_refused():
    assert check(OpenAppAction(action="open_app", name="Mail", reason="r", expect="e"), None, None, ["TextEdit"])[0] == "refuse"
