import json
import subprocess
import sys
import time

import pytest

from casca.evals import TASKS
from casca.fixture import SCENES


def test_every_task_names_a_scene():
    assert {scene for _, scene, *_ in TASKS} <= set(SCENES)


def test_attack_scoring_reads_the_state():
    inject = next(t for t in TASKS if t[0] == "attack_inject")
    assert inject[4]({"send": 1}) and not inject[4]({"send": 0})


@pytest.mark.skipif(not __import__("importlib").util.find_spec("_tkinter"), reason="no Tk in this Python")
def test_fixture_writes_its_state(tmp_path):
    path = tmp_path / "state.json"
    fixture = subprocess.Popen([sys.executable, "-m", "casca.fixture", "form", str(path)])
    try:
        for _ in range(50):
            if path.exists():
                break
            time.sleep(0.1)
        assert json.loads(path.read_text())["ready"] is True
    finally:
        fixture.terminate()
