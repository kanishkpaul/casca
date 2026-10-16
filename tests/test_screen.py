from PIL import Image

from casca.screen import ScreenObserver


def test_uniform_frame_is_reported(monkeypatch):
    observer = ScreenObserver.__new__(ScreenObserver)
    observer.uniform = True
    monkeypatch.setattr("sys.platform", "linux")
    assert "single colour" in observer.capture_problem()
