import pytest

from casca.safety import SafetyPolicy


@pytest.mark.parametrize("task", ["Open the form and fill in my name", "Show information about the weather",
                                  "Open the riverbank photo"])
def test_ordinary_tasks_are_not_blocked(task):
    assert SafetyPolicy().check_task(task) == (True, None)


def test_a_whole_keyword_still_blocks():
    assert SafetyPolicy().check_task("Type my password into the vault")[0] is False
