import pytest

from casca.safety import SafetyPolicy


@pytest.mark.parametrize("task", ["Open the form and fill in my name", "Show information about the weather",
                                  "Open the riverbank photo"])
def test_ordinary_tasks_are_not_blocked(task):
    assert SafetyPolicy().check_task(task) == (True, None)


def test_a_whole_keyword_still_blocks():
    assert SafetyPolicy().check_task("Type my password into the vault")[0] is False


from casca.actions import HotkeyAction, TypeAction


def typing(text):
    return SafetyPolicy().check_action(TypeAction(action="type", text=text, reason="r"), "t")[0]


def test_quit_chord_is_blocked_unless_unsafe():
    quit_ = HotkeyAction(action="hotkey", keys=["cmd", "q"], reason="r")
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
