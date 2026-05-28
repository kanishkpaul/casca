import mss
from PIL import Image
import io
from pathlib import Path
from casca.utils import encode_image_base64
from casca.config import config

class ScreenObserver:
    def __init__(self, monitor_index: int = config.MONITOR_INDEX, max_width: int = config.SCREENSHOT_MAX_WIDTH):
        self.monitor_index = monitor_index
        self.max_width = max_width
        self.sct = mss.mss()
        # verify monitor index
        monitors = self.sct.monitors
        if self.monitor_index >= len(monitors):
            raise ValueError(f"Monitor {self.monitor_index} not found. Available: {len(monitors)-1}")
            
    def get_screen_size(self) -> dict:
        monitor = self.sct.monitors[self.monitor_index]
        return {
            "width": monitor["width"],
            "height": monitor["height"]
        }

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        if img.width > self.max_width:
            ratio = self.max_width / img.width
            new_height = int(img.height * ratio)
            return img.resize((self.max_width, new_height), Image.Resampling.LANCZOS)
        return img

    def screenshot(self, path: str | Path | None = None) -> bytes:
        monitor = self.sct.monitors[self.monitor_index]
        sct_img = self.sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        if path:
            img.save(path, format="PNG")
            
        img = self._resize_if_needed(img)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

    def screenshot_base64(self, path: str | Path | None = None) -> str:
        img_bytes = self.screenshot(path)
        return encode_image_base64(img_bytes)
