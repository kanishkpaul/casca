import pytest

from casca.actions import HotkeyAction, TypeAction
from casca.safety import SafetyPolicy


def typing(text):
    return SafetyPolicy().check_action(TypeAction(action="type", text=text, reason="r", expect="e"), "t")[0]


def test_quit_chord_is_blocked_unless_unsafe():
    quit_ = HotkeyAction(action="hotkey", keys=["cmd", "q"], reason="r", expect="e")
    assert SafetyPolicy().check_action(quit_, "t")[0] is False
    assert SafetyPolicy(unsafe=True).check_action(quit_, "t")[0] is True


@pytest.mark.parametrize("text, allowed", [
    ("hello world", True),
    ("call 4111 1111 1111 1111 now", False),
    ("order 1234567890123", True),
    ("sk-abcdefghijklmnopqrstuvwx", False),
])
def test_secrets_are_not_typed(text, allowed):
    assert typing(text) is allowed
