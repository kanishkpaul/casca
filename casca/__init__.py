import sys

if sys.platform == "win32":
    # Must run before pyautogui or mss is imported: each sets a different DPI awareness on
    # import, a process can set it once, and a mismatch makes capture and clicks disagree on
    # monitors scaled differently. -4 is DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2.
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

__version__ = "0.1.0"
