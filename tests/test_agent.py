from casca.models.mock_provider import MockVisionProvider
from tests.conftest import FakeDesktop


def test_mock_run_executes_every_step(run_agent):
    desktop = FakeDesktop()
    _, steps = run_agent(MockVisionProvider(), desktop=desktop)
    assert [s["action"]["action"] for s in steps] == ["move_mouse", "click", "done"]
    assert len(desktop.actions) == 3
