import pytest
from pyautogui import FailSafeException

from casca.models.mock_provider import MockVisionProvider
from tests.conftest import FakeDesktop, ScriptedModel


def test_mock_run_executes_every_step(run_agent):
    desktop = FakeDesktop()
    _, steps = run_agent(MockVisionProvider(), desktop=desktop)
    assert [s["action"]["action"] for s in steps] == ["move_mouse", "click", "done"]
    assert len(desktop.actions) == 3


def test_model_text_with_markup_does_not_crash(run_agent):
    reply = '{"action": "done", "answer": "closing [/b] tag", "reason": "[/red] too"}'
    _, steps = run_agent(ScriptedModel(reply), task="say [/x]")
    assert steps[0]["action"]["answer"] == "closing [/b] tag"


def test_null_model_content_stops_cleanly(run_agent):
    run_agent(ScriptedModel({"raw_output": None}))


DONE = '{"action": "done", "answer": "ok", "reason": "r"}'
CLICK = '{"action": "click", "x": 10, "y": 10, "reason": "r"}'


@pytest.mark.parametrize("reply, outcome", [
    ({"error": "401"}, "model_error"),
    ("not json", "parse_error"),
    (DONE, "done"),
])
def test_every_ending_is_logged_with_an_outcome(run_agent, reply, outcome):
    meta, steps = run_agent(ScriptedModel(reply))
    assert meta["outcome"] == outcome and "end_time" in meta
    assert len(steps) == 1


def test_execution_error_is_recorded_and_the_run_continues(run_agent):
    meta, steps = run_agent(ScriptedModel(CLICK, DONE), desktop=FakeDesktop(fail=OSError("no input")))
    assert steps[0]["execution"] == {"status": "error", "error": "OSError: no input"}
    assert meta["outcome"] == "done"


def test_fail_safe_interrupts_and_finalizes(run_agent):
    meta, steps = run_agent(ScriptedModel(CLICK), desktop=FakeDesktop(fail=FailSafeException()))
    assert meta["outcome"] == "interrupted"
    assert steps[0]["execution"]["status"] == "interrupted"


def test_max_steps_is_an_outcome(run_agent):
    meta, _ = run_agent(ScriptedModel(CLICK, CLICK), max_steps=2)
    assert meta["outcome"] == "max_steps"
