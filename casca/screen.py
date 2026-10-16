import mss
import sys

from PIL import Image, ImageStat
import io
from pathlib import Path
from casca.utils import encode_image_base64
from casca.config import config

class ScreenObserver:
    def __init__(self, monitor_index: int = config.MONITOR_INDEX, max_width: int = config.SCREENSHOT_MAX_WIDTH):
        self.monitor_index = monitor_index
        self.max_width = max_width
        self.sct = mss.MSS()
        monitors = self.sct.monitors
        # Index 0 is every monitor combined, which has no single scale or origin to map clicks to.
        if not 1 <= self.monitor_index < len(monitors):
            raise ValueError(f"Monitor {self.monitor_index} not found. Use 1 to {len(monitors) - 1}.")
            
    def get_screen_size(self) -> dict:
        monitor = self.sct.monitors[self.monitor_index]
        return {k: monitor[k] for k in ("left", "top", "width", "height")}

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        if img.width > self.max_width:
            ratio = self.max_width / img.width
            new_height = int(img.height * ratio)
            return img.resize((self.max_width, new_height), Image.Resampling.LANCZOS)
        return img

    def capture_problem(self) -> str | None:
        """Why the last capture cannot be trusted, with the fix, or None."""
        if sys.platform == "darwin":
            import Quartz
            if not Quartz.CGPreflightScreenCaptureAccess():
                return ("Screen Recording is not granted to this terminal. Enable it in System Settings > "
                        "Privacy & Security > Screen Recording, then restart the terminal.")
        if self.uniform:
            return "The screenshot is a single colour. Check screen capture permission, or that the display is awake."
        return None

    def screenshot(self, path: str | Path | None = None) -> bytes:
        monitor = self.sct.monitors[self.monitor_index]
        sct_img = self.sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        self.capture_size = sct_img.size
        
        if path:
            img.save(path, format="PNG")
            
        img = self._resize_if_needed(img)
        self.image_size = img.size
        self.uniform = ImageStat.Stat(img.convert("L")).stddev[0] < 2
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

    def screenshot_base64(self, path: str | Path | None = None) -> str:
        img_bytes = self.screenshot(path)
        return encode_image_base64(img_bytes)
