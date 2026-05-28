import json
import os
from datetime import datetime
from pathlib import Path

class RunLogger:
    def __init__(self, log_dir: str = "logs"):
        self.base_dir = Path(log_dir)
        self.run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.run_dir = self.base_dir / self.run_id
        self.screenshots_dir = self.run_dir / "screenshots"
        
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.steps_file = self.run_dir / "steps.jsonl"
        self.metadata_file = self.run_dir / "metadata.json"

    def log_metadata(self, task: str, max_steps: int, model: str):
        metadata = {
            "run_id": self.run_id,
            "task": task,
            "max_steps": max_steps,
            "model": model,
            "start_time": datetime.now().isoformat()
        }
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def log_step(self, step: int, task: str, screenshot_bytes: bytes, model_raw: str, action: dict, safety: dict, execution: dict):
        screenshot_filename = f"step_{step:03d}.png"
        screenshot_path = self.screenshots_dir / screenshot_filename
        
        with open(screenshot_path, "wb") as f:
            f.write(screenshot_bytes)
            
        step_log = {
            "step": step,
            "task": task,
            "screenshot": f"screenshots/{screenshot_filename}",
            "model_raw": model_raw,
            "action": action,
            "safety": safety,
            "execution": execution,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.steps_file, "a") as f:
            f.write(json.dumps(step_log) + "\n")
