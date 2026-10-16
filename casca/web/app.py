import re

from flask import Flask, abort, render_template, send_from_directory
from pathlib import Path
from casca.replay import load_run
from casca.config import config

app = Flask(__name__)
LOG_DIR = Path(config.LOG_DIR)
RUN_ID = re.compile(r"run_\d{8}_\d{6}(_[0-9a-f]{4})?")


def run_dir(run_id: str) -> Path:
    """Only names the logger writes, so a URL cannot reach outside the logs directory."""
    if not RUN_ID.fullmatch(run_id) or not (LOG_DIR / run_id).is_dir():
        abort(404)
    return LOG_DIR / run_id

@app.route("/")
def index():
    runs = []
    if LOG_DIR.exists():
        for run_dir in sorted(LOG_DIR.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "metadata.json").exists():
                try:
                    metadata, _ = load_run(run_dir)
                    runs.append(metadata)
                except Exception as e:
                    runs.append({"run_id": run_dir.name, "task": f"Could not load this run: {e}"})
    return render_template("index.html", runs=runs)

@app.route("/run/<run_id>")
def view_run(run_id):
    path = run_dir(run_id)
    try:
        metadata, steps = load_run(path)
    except Exception as e:
        return str(e), 500
        
    return render_template("run.html", metadata=metadata, steps=steps, run_id=run_id)

@app.route("/run/<run_id>/screenshots/<path:filename>")
def view_screenshot(run_id, filename):
    return send_from_directory(run_dir(run_id) / "screenshots", filename)

if __name__ == "__main__":
    app.run(debug=True)
