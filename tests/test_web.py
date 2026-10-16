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


@pytest.mark.parametrize("url", ["/run/..", "/run/../screenshots/leak.txt", "/run/nope"])
def test_paths_outside_the_logs_directory_are_not_found(client, tmp_path, url):
    (tmp_path.parent / "screenshots").mkdir(exist_ok=True)
    (tmp_path.parent / "screenshots" / "leak.txt").write_text("secret")
    assert client.get(url).status_code == 404


def test_corrupt_run_is_listed_with_the_reason(client, tmp_path):
    bad = tmp_path / "run_20261016_221805_0000"
    bad.mkdir()
    (bad / "metadata.json").write_text("{")
    assert b"Could not load this run" in client.get("/").data
