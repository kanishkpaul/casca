from flask import Flask, render_template, abort
from pathlib import Path
from casca.replay import load_run
from casca.config import config

app = Flask(__name__)
LOG_DIR = Path(config.LOG_DIR)

@app.route("/")
def index():
    runs = []
    if LOG_DIR.exists():
        for run_dir in sorted(LOG_DIR.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "metadata.json").exists():
                try:
                    metadata, _ = load_run(run_dir)
                    runs.append(metadata)
                except Exception:
                    pass
    return render_template("index.html", runs=runs)

@app.route("/run/<run_id>")
def view_run(run_id):
    run_dir = LOG_DIR / run_id
    if not run_dir.exists():
        abort(404)
        
    try:
        metadata, steps = load_run(run_dir)
    except Exception as e:
        return str(e), 500
        
    return render_template("run.html", metadata=metadata, steps=steps, run_id=run_id)

@app.route("/run/<run_id>/screenshots/<path:filename>")
def view_screenshot(run_id, filename):
    from flask import send_from_directory
    screenshots_dir = LOG_DIR / run_id / "screenshots"
    return send_from_directory(screenshots_dir, filename)

if __name__ == "__main__":
    app.run(debug=True)
