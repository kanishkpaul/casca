import asyncio

from casca.agent import CascaAgent
from casca.app import CascaApp
from tests.conftest import FakeDesktop, FakeScreen, ScriptedModel

CLICK = '{"action": "click", "x": 640, "y": 416, "reason": "r", "expect": "the menu opens"}'
DONE = '{"action": "done", "answer": "menu opened", "reason": "r", "previous": "held"}'


def run_app(tmp_path, desktop, *keys):
    model = ScriptedModel(CLICK, DONE)
    app = CascaApp(lambda ui: CascaAgent(model, screen=FakeScreen(), desktop=desktop, log_dir=str(tmp_path),
                                         settle_timeout=0, ui=ui), "scripted", "local", str(tmp_path))

    async def drive():
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press(*"open the menu", "enter")
            for key in keys:
                await pilot.pause(0.3)
                await pilot.press(key)
            for _ in range(50):
                await pilot.pause(0.1)
                if app.mode == "idle" and app.agent:
                    break
            return "\n".join(str(line.text) for line in app.query_one("#log").lines)

    return asyncio.run(drive())


def test_a_task_runs_from_the_prompt_to_ok(tmp_path):
    log = run_app(tmp_path, FakeDesktop())
    assert "❯ open the menu" in log and "click" in log and "ok done in 2 steps" in log


def test_a_gate_waits_for_a_key_and_enter_denies(tmp_path):
    send = FakeDesktop(element={"app": "Mail", "role": "AXButton", "name": "Send", "secure": False})
    log = run_app(tmp_path, send, "enter")
    assert "approve?" in log and send.actions[-1].action == "done" and len(send.actions) == 1
