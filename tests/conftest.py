import io

import pytest
from PIL import Image

from casca.agent import CascaAgent
from casca.models.base import VisionActionModel
from casca.replay import load_run


class FakeScreen:
    def __init__(self, image_size=(1280, 832), monitor=None, color="white"):
        self.image_size = image_size
        self.size = monitor or {"left": 0, "top": 0, "width": 1470, "height": 956}
        self.color = color

    def capture_problem(self):
        return "blank" if self.color == "black" else None

    def get_screen_size(self):
        return self.size

    def screenshot(self, path=None):
        buf = io.BytesIO()
        Image.new("RGB", self.image_size, self.color).save(buf, "PNG")
        return buf.getvalue()


class FakeDesktop:
    def __init__(self, fail=None, problem=None):
        self.actions, self.fail, self.problem = [], fail, problem

    def input_problem(self):
        return self.problem

    def execute_action(self, action):
        self.actions.append(action)
        if self.fail:
            raise self.fail
        return {"status": "success"}


class ScriptedModel(VisionActionModel):
    """Replies in order; a dict is returned as is, a string as raw output."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.histories = []

    def propose_action(self, task, screenshot_bytes, step_index, history, screen):
        self.histories.append(history)
        reply = self.replies.pop(0)
        return reply if isinstance(reply, dict) else {"raw_output": reply}


@pytest.fixture
def run_agent(tmp_path):
    def run(model, task="open the menu", desktop=None, **kw):
        agent = CascaAgent(model, screen=FakeScreen(), desktop=desktop or FakeDesktop(),
                           log_dir=str(tmp_path), step_delay=0, **kw)
        agent.run(task)
        runs = list(tmp_path.iterdir())
        return load_run(runs[0]) if runs else (None, [])
    return run
