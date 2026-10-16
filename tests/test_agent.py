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
CLICK = '{"action": "click", "x": 10, "y": 10, "reason": "r", "expect": "e"}'


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
    run_agent(ScriptedModel('{"action": "click", "x": 640, "y": 416, "reason": "r", "expect": "e"}', DONE), desktop=desktop)
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
    assert entry["action"] == {"action": "click", "x": 10, "y": 10, "reason": "r", "expect": "e", "previous": None}
    assert entry["execution"]["error"] == "OSError: no input"


def test_blank_screen_stops_before_the_model_is_asked(tmp_path):
    from casca.agent import CascaAgent
    from tests.conftest import FakeScreen
    model = ScriptedModel(DONE)
    outcome = CascaAgent(model, screen=FakeScreen(color="black"), desktop=FakeDesktop(), log_dir=str(tmp_path)).run("t")
    assert outcome == "blank_screen" and model.histories == []


def test_norm1000_points_map_to_screen_points(run_agent):
    desktop, model = FakeDesktop(), ScriptedModel('{"action": "click", "x": 500, "y": 500, "reason": "r", "expect": "e"}', DONE)
    run_agent(model, desktop=desktop, coords="norm1000")
    assert (desktop.actions[0].x, desktop.actions[0].y) == (735, 478)


def test_missing_input_permission_stops_before_acting(run_agent):
    model = ScriptedModel(CLICK)
    meta, _ = run_agent(model, desktop=FakeDesktop(problem="no Accessibility"))
    assert meta["outcome"] == "no_input" and model.histories == []


def test_the_same_click_three_times_is_stuck(run_agent):
    meta, steps = run_agent(ScriptedModel(CLICK, CLICK, CLICK, DONE))
    assert meta["outcome"] == "stuck" and len(steps) == 3


def test_previous_verdict_is_attached_to_the_last_act(run_agent):
    model = ScriptedModel(CLICK, '{"action": "done", "answer": "a", "reason": "r", "previous": "not_held"}')
    run_agent(model)
    assert model.histories[1][0]["verified"] == "not_held"


def test_unchanged_screen_is_recorded(run_agent):
    _, steps = run_agent(ScriptedModel(CLICK, DONE))
    assert steps[0]["execution"]["changed"] is False


def test_time_budget_stops_the_run(run_agent):
    meta, _ = run_agent(ScriptedModel(CLICK, DONE), max_seconds=-1)
    assert meta["outcome"] == "time_budget"


def test_confirm_without_a_terminal_is_a_refused_step(run_agent):
    send = {"app": "Mail", "role": "AXButton", "name": "Send", "secure": False}
    desktop = FakeDesktop(element=send)
    meta, steps = run_agent(ScriptedModel(CLICK, DONE), desktop=desktop)
    assert steps[0]["execution"]["status"] == "refused" and desktop.actions[-1].action == "done"
    assert steps[0]["safety"]["gate"] == "confirm"


def test_stop_keys_stop_before_the_next_act(run_agent):
    desktop = FakeDesktop()
    desktop.stop = True
    model = ScriptedModel(CLICK)
    model.propose_action = (lambda f: lambda *a: __import__("time").sleep(0.2) or f(*a))(model.propose_action)
    meta, steps = run_agent(model, desktop=desktop)
    assert meta["outcome"] == "stopped" and desktop.actions == []


def test_moving_the_mouse_takes_over(run_agent):
    desktop = FakeDesktop()
    model = ScriptedModel(CLICK, '{"action": "press", "key": "a", "reason": "r", "expect": "e"}')
    # The user moves the mouse while the model thinks about the second step.
    model.propose_action = (lambda f: lambda *a: (len(model.histories) == 1 and setattr(desktop, "pointer", (300, 300)))
                            or f(*a))(model.propose_action)
    meta, _ = run_agent(model, desktop=desktop)
    assert meta["outcome"] == "taken_over" and len(desktop.actions) == 1


def test_handback_without_a_terminal_ends_the_run(run_agent):
    meta, _ = run_agent(ScriptedModel('{"action": "handback", "reason": "sign in"}'))
    assert meta["outcome"] == "handed_back"


def test_trace_records_geometry_point_and_bytes(run_agent):
    model = ScriptedModel({"raw_output": '{"action": "click", "x": 640, "y": 416, "reason": "r", "expect": "e"}', "sent_bytes": 1234}, DONE)
    meta, steps = run_agent(model)
    assert steps[0]["image_size"] == [1280, 832] and steps[0]["sent_bytes"] == 1234
    assert steps[0]["screen_point"] == {"x": 735, "y": 478}
    assert meta["monitor"]["width"] == 1470 and meta["destination"] == "none"
