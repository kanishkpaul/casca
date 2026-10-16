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
