import os
from dotenv import load_dotenv
from platformdirs import user_data_dir

load_dotenv()


def _number(name: str, default: str, kind=int):
    value = os.getenv(name, default)
    try:
        return kind(value)
    except ValueError:
        raise ValueError(f"{name}={value!r} must be a number") from None

class Config:
    # Any OpenAI-compatible endpoint. For a local model, e.g. Ollama:
    # CASCA_BASE_URL=http://localhost:11434/v1 CASCA_MODEL=qwen3-vl:8b, and no key.
    BASE_URL = os.getenv("CASCA_BASE_URL", "https://router.huggingface.co/v1")
    MODEL = os.getenv("CASCA_MODEL") or os.getenv("HF_MODEL_ID", "google/gemma-4-31b-it")
    API_KEY = os.getenv("CASCA_API_KEY") or os.getenv("HF_API_TOKEN")
    # How the model names points: "image_px" (pixels of the screenshot) or "norm1000"
    # (0 to 1000 on each axis, as Qwen3-VL does).
    COORDS = os.getenv("CASCA_COORDS", "image_px")
    
    MAX_STEPS = _number("CASCA_MAX_STEPS", "20")
    MONITOR_INDEX = _number("CASCA_MONITOR", "1")
    SCREENSHOT_MAX_WIDTH = _number("CASCA_SCREENSHOT_MAX_WIDTH", "1280")
    STEP_DELAY = _number("CASCA_STEP_DELAY", "0.5", float)
    
    LOG_DIR = os.getenv("CASCA_LOG_DIR") or os.path.join(user_data_dir("casca"), "logs")

config = Config()
