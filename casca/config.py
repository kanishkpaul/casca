import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    HF_API_TOKEN = os.getenv("HF_API_TOKEN")
    HF_MODEL_ID = os.getenv("HF_MODEL_ID", "google/gemma-4-31b-it")
    HF_API_URL = os.getenv("HF_API_URL")
    
    MAX_STEPS = int(os.getenv("CASCA_MAX_STEPS", "20"))
    MONITOR_INDEX = int(os.getenv("CASCA_MONITOR", "1"))
    SCREENSHOT_MAX_WIDTH = int(os.getenv("CASCA_SCREENSHOT_MAX_WIDTH", "1280"))
    STEP_DELAY = float(os.getenv("CASCA_STEP_DELAY", "0.5"))
    
    LOG_DIR = os.getenv("CASCA_LOG_DIR", "logs")

config = Config()
