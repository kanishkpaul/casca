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
    run_agent(ScriptedModel(*[{"raw_output": None}] * 3))


DONE = '{"action": "done", "answer": "ok", "reason": "r"}'
CLICK = '{"action": "click", "x": 10, "y": 10, "reason": "r"}'


@pytest.mark.parametrize("reply, outcome", [
    ({"error": "401"}, "model_error"),
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


def test_dry_run_reports_skipped_not_success(run_agent):
    _, steps = run_agent(ScriptedModel(CLICK, DONE), dry_run=True)
    assert steps[0]["execution"] == {"status": "skipped"}


def test_click_reaches_the_desktop_in_screen_points(run_agent):
    desktop = FakeDesktop()
    run_agent(ScriptedModel('{"action": "click", "x": 640, "y": 416, "reason": "r"}', DONE), desktop=desktop)
    assert (desktop.actions[0].x, desktop.actions[0].y) == (735, 478)


def test_malformed_reply_is_retried_with_the_error(run_agent):
    model = ScriptedModel('{"action": "click", "x": "left", "reason": "r"}', DONE)
    run_agent(model)
    assert "click.x" in model.histories[1][-1]["execution"]["error"]


def test_three_bad_replies_end_with_parse_error(run_agent):
    meta, steps = run_agent(ScriptedModel("no", "still no", '{"a": 1} {"b": 2}'))
    assert meta["outcome"] == "parse_error" and steps[0]["execution"]["status"] == "parse_error"


def test_first_of_two_json_objects_is_used(run_agent):
    meta, _ = run_agent(ScriptedModel(DONE + ' {"extra": true}'))
    assert meta["outcome"] == "done"


def test_history_carries_arguments_reason_and_error(run_agent):
    model = ScriptedModel(CLICK, DONE)
    run_agent(model, desktop=FakeDesktop(fail=OSError("no input")))
    entry = model.histories[1][0]
    assert entry["action"] == {"action": "click", "x": 10, "y": 10, "reason": "r"}
    assert entry["execution"]["error"] == "OSError: no input"
