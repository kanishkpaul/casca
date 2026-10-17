from typer.testing import CliRunner

from casca import cli
from tests.conftest import ScriptedModel

DONE = '{"action": "done", "answer": "all done", "reason": "r"}'


def test_trace_lists_and_replays_runs(run_agent, tmp_path, monkeypatch):
    run_agent(ScriptedModel('{"action": "press", "key": "a", "reason": "r", "expect": "e"}', DONE), task="press a")
    monkeypatch.setattr(cli.config, "LOG_DIR", str(tmp_path))
    listing = CliRunner().invoke(cli.app, ["trace"]).output
    assert "done" in listing and "press a" in listing
    run_id = listing.split()[0]
    replay = CliRunner().invoke(cli.app, ["trace", run_id]).output
    assert "key       a" in replay and "all done" in replay
