import json

import pytest

from casca.web import app as viewer


@pytest.fixture
def client(tmp_path, monkeypatch):
    run = tmp_path / "run_20261016_221804_7f3a"
    (run / "screenshots").mkdir(parents=True)
    (run / "metadata.json").write_text(json.dumps({"run_id": run.name, "task": "t", "model": "m", "start_time": "s"}))
    (run / "steps.jsonl").write_text("")
    monkeypatch.setattr(viewer, "LOG_DIR", tmp_path)
    return viewer.app.test_client()


def test_index_lists_runs(client):
    assert b"run_20261016_221804_7f3a" in client.get("/").data
