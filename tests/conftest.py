import io

import pytest
from PIL import Image

from casca.agent import CascaAgent
from casca.models.base import VisionActionModel
from casca.replay import load_run


class FakeScreen:
    def __init__(self, width=1470, height=956, color="white"):
        self.size = {"width": width, "height": height}
        self.color = color

    def get_screen_size(self):
        return self.size

    def screenshot(self, path=None):
        buf = io.BytesIO()
        Image.new("RGB", (64, 40), self.color).save(buf, "PNG")
        return buf.getvalue()


class FakeDesktop:
    def __init__(self, fail=None):
        self.actions, self.fail = [], fail

    def execute_action(self, action):
        self.actions.append(action)
        if self.fail:
            raise self.fail
        return {"status": "success"}


class ScriptedModel(VisionActionModel):
    """Replies in order; a dict is returned as is, a string as raw output."""

    def __init__(self, *replies):
        self.replies = list(replies)

    def propose_action(self, task, screenshot_bytes, step_index, history, screen):
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
