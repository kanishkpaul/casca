import io
import json

from casca.ui import JsonlUI, LineUI
from tests.conftest import FakeDesktop, ScriptedModel

CLICK = '{"action": "click", "x": 640, "y": 416, "reason": "r", "expect": "the menu opens"}'
DONE = '{"action": "done", "answer": "opened [/b] it", "reason": "r", "previous": "held"}'


def test_jsonl_prints_one_object_per_event(run_agent, capsys):
    run_agent(ScriptedModel(CLICK, DONE), ui=JsonlUI())
    events = [json.loads(line)["event"] for line in capsys.readouterr().out.splitlines()]
    assert events[0] == "start" and events[-1] == "end" and "act" in events and "verify" in events


def test_line_mode_draws_rows_without_reading_model_text_as_markup(run_agent):
    ui = LineUI("never")
    ui.out.file = io.StringIO()
    element = {"app": "TextEdit", "role": "AXButton", "name": "Format", "secure": False}
    run_agent(ScriptedModel(CLICK, DONE), ui=ui, desktop=FakeDesktop(element=element))
    out = ui.out.file.getvalue()
    assert '┊ ↖ click     "Format" in TextEdit' in out
    assert "verify    the menu opens  held" in out and "opened [/b] it" in out and out.splitlines()[-1].startswith("ok done in 2 steps")
