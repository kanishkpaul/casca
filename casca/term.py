"""Casca's terminal look, read from the design kit's tokens rather than copied: the shell skin's
terminal palette and Casca's identity. Colour detection follows design/system/TUI.md."""
import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

HERE = Path(__file__).parent
# Wheels carry the tokens as casca/tokens.json; a checkout reads them from design/.
TOKENS = json.loads(next(p for p in (HERE / "tokens.json", HERE.parent / "design/tokens/tokens.json") if p.exists()).read_text())
IDENTITY = TOKENS["identities"]["casca"]
PALETTES = TOKENS["skins"][IDENTITY["defaultSkin"]]["tui"]


def color_system(flag: str = "auto", stream=sys.stdout) -> str | None:
    """None for no colour, else "256" or "truecolor". --color always or never overrides the rest."""
    if flag == "never" or (flag == "auto" and os.getenv("NO_COLOR")):
        return None
    if flag == "auto" and not os.getenv("CLICOLOR_FORCE") and (not stream.isatty() or os.getenv("TERM") == "dumb"):
        return None
    return "truecolor" if os.getenv("COLORTERM") in ("truecolor", "24bit") else "256"


def polarity() -> str:
    """Light terminals get the skin's light palette, never an inversion of the dark one."""
    if (choice := os.getenv("CASCA_THEME")) in ("light", "dark"):
        return choice
    if fgbg := os.getenv("COLORFGBG"):
        return "light" if fgbg.split(";")[-1] in ("7", "15") else "dark"
    return "light" if os.getenv("TERM_PROGRAM") == "Apple_Terminal" else "dark"


def make_console(flag: str = "auto", stderr: bool = False) -> Console:
    palette = PALETTES[polarity()]
    styles = {**palette, "status": f"{palette['status_bar_text']} on {palette['status_bar_bg']}"}
    system = color_system(flag, sys.stderr if stderr else sys.stdout)
    return Console(theme=Theme(styles), color_system=system, no_color=system is None, highlight=False, stderr=stderr)
