from pathlib import Path
import json

def load_run(run_dir: str | Path):
    path = Path(run_dir)
    metadata_path = path / "metadata.json"
    steps_path = path / "steps.jsonl"
    
    if not metadata_path.exists() or not steps_path.exists():
        raise FileNotFoundError(f"Run {path} is incomplete or does not exist.")
        
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
        
    steps = []
    with open(steps_path, "r") as f:
        for line in f:
            if line.strip():
                steps.append(json.loads(line))
                
    return metadata, steps
