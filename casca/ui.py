"""How a run reaches the user. The agent emits events and asks two questions; a UI decides how
they look. Text from the model or the screen goes into rich Text objects, never markup."""
import json
import platform
import sys

from rich.text import Text

from casca import __version__, term

# Icon and verb per action, from the fixed verb list in design/README.md.
# Single-width symbols only: emoji such as 👆 take two cells in most terminals and break the columns.
VERBS = {"click": ("↖", "click"), "double_click": ("↖", "click"), "right_click": ("↖", "click"),
         "drag": ("↘", "drag"), "move_mouse": ("↗", "point"), "type": ("⌨", "type"), "press": ("⏎", "key"),
         "hotkey": ("⏎", "key"), "scroll": ("↕", "scroll"), "wait": ("◷", "wait"), "open_app": ("▣", "open"),
         "done": ("✓", "done"), "fail": ("✗", "fail"), "handback": ("⇄", "hand back")}
ENDS_OK, ENDS_BY_USER = {"done"}, {"stopped", "taken_over", "handed_back", "aborted", "interrupted"}


class UI:
    """Silent, and says no to every question: what tests and evals use."""

    def emit(self, event: str, **fields) -> None:
        pass

    def approve(self, action: dict, reason: str, element: dict | None = None) -> bool:
        return False

    def pause(self, reason: str) -> bool:
        return False


class JsonlUI(UI):
    """One JSON object per event, for scripts. Never colour, never a question."""

    def emit(self, event: str, **fields) -> None:
        print(json.dumps({"event": event, **fields}, default=str, ensure_ascii=False), flush=True)


def detail(action: dict, element: dict | None = None) -> str:
    """The exact argument: the control's name from the OS when there is one, else the point."""
    kind = action["action"]
    if element and element.get("name") and ("x" in action or "x1" in action):
        return f"\"{element['name']}\" in {element['app']}"
    return {"type": lambda: f"\"{action['text']}\"", "press": lambda: action["key"],
            "hotkey": lambda: "+".join(action["keys"]), "scroll": lambda: f"{action['amount']:+d} notches",
            "wait": lambda: f"{action['ms']} ms", "open_app": lambda: action["name"],
            "done": lambda: action.get("answer", ""), "fail": lambda: action["reason"],
            "handback": lambda: action["reason"]}.get(
        kind, lambda: f"({action.get('x', action.get('x1'))}, {action.get('y', action.get('y1'))})")()


class LineUI(UI):
    """design/system/TUI.md line mode: metadata line, response label, tool rows, spinner, the gate box."""

    def __init__(self, color: str = "auto"):
        self.out, self.spinner = term.make_console(color), None

    def write(self, text: Text) -> None:
        self.out.print(text)

    def _row(self, icon: str, verb: str, text: str, tail: str | None = None, failed: bool = False) -> None:
        row = Text("  ").append("┊", "banner_border").append(f" {icon} ").append(f"{verb:9}", "ui_error" if failed else "ui_label")
        row.append(f" {text}")
        if tail:
            row.append(f"  {tail}", "ui_error" if failed else "banner_dim")
        self.write(row)

    def _box(self, style: str, title: str, lines: list[tuple[str, str]], footer: str) -> None:
        width = max(len(title) + 4, len(footer) + 4, *(len(t) + 4 for t, _ in lines))
        self.write(Text(f"  ╭─ {title} " + "─" * (width - len(title) - 3) + "╮", style))
        for text, tone in lines:
            self.write(Text("  │ ", style).append(text.ljust(width - 1), tone).append("│", style))
        self.write(Text(f"  ╰─ {footer} " + "─" * (width - len(footer) - 3) + "╯", style))

    def _spin(self, verb: str | None) -> None:
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        if verb and self.out.is_terminal:
            self.spinner = self.out.status(Text(f"{term.IDENTITY['glyph']} {verb}…", "banner_dim"), spinner="dots",
                                           spinner_style="ui_accent")
            self.spinner.start()

    def emit(self, event: str, **f) -> None:
        self._spin(None)
        if event == "start":
            where = "local" if f["destination"] in ("127.0.0.1", "localhost", "none") else f"your key: {f['destination']}"
            parts = [f"{term.IDENTITY['glyph']} casca v{__version__}", f["model"], where, {"Darwin": "macOS"}.get(platform.system(), platform.system())]
            self.write(Text(" · ".join(parts + (["dry run"] if f["dry_run"] else [])), "banner_dim"))
            self.write(Text(f" {term.IDENTITY['glyph']} {term.IDENTITY['agent']} ", "bold response_border"))
        elif event == "think":
            self._spin("reading the screen" if f["step"] == 0 else "locating")
        elif event == "observe":
            self._row("◎", "read", f"screenshot {f['image_size'][0]}×{f['image_size'][1]}")
        elif event == "invalid_reply":
            self._row("✗", "reply", f["problem"][:80], "invalid, asking again", failed=True)
        elif event == "verify":
            self._row("✓", "verify", f["expect"], "held" if f["verdict"] == "held" else f["verdict"].replace("_", " "),
                      failed=f["verdict"] == "not_held")
        elif event in ("act", "refused"):
            icon, verb = VERBS.get(f["action"]["action"], ("·", f["action"]["action"]))
            result = f.get("result", {})
            failed = event == "refused" or result.get("status") not in ("success", "skipped")
            tail = f["reason"] if event == "refused" else result.get("error") or (
                "dry run" if result.get("status") == "skipped" else f"{result['settle_s']}s" if "settle_s" in result else None)
            if f["action"]["action"] not in ("done", "fail", "handback"):
                self._row(icon, verb, detail(f["action"], f.get("element")), tail, failed)
        elif event == "end":
            outcome = f["outcome"]
            message = f.get("message") or outcome.replace("_", " ")
            if outcome in ENDS_OK:
                self.write(Text("  " + message))
                self.write(Text("ok ", "ui_ok").append(f"done in {f['steps']} steps · {f['seconds']:.0f} s · "
                                                            f"{f['sent_bytes'] / 1000:.0f} KB sent"))
            else:
                tone = "ui_warn" if outcome in ENDS_BY_USER else "ui_error"
                self.write(Text(f"{'stopped' if outcome in ENDS_BY_USER else 'error'}: ", tone).append(message))
                trace = f" · trace {f['run_id']}" if f.get("run_id") else ""
                self.write(Text(f"  outcome {outcome} after {f['steps']} steps{trace}", "banner_dim"))

    def approve_box(self, action: dict, reason: str, element: dict | None = None) -> None:
        verb = VERBS.get(action["action"], ("·", action["action"]))[1]
        self._box("ui_warn", "approve?", [(f"{verb}  {detail(action, element)}", "banner_text"), (reason, "banner_dim")],
                  "[y] approve once · [n/enter] deny")

    def pause_box(self, reason: str, footer: str = "[enter] I'm done · type stop to end") -> None:
        self._box("ui_label", "your turn", [(reason, "banner_text"), ("Casca carries on from a fresh screenshot.", "banner_dim")],
                  footer)

    def approve(self, action: dict, reason: str, element: dict | None = None) -> bool:
        if not sys.stdin.isatty():
            return False
        self._spin(None)
        self.approve_box(action, reason, element)
        return self.out.input("  > ").strip().lower() == "y"

    def pause(self, reason: str) -> bool:
        if not sys.stdin.isatty():
            return False
        self._spin(None)
        self.pause_box(reason)
        return self.out.input("  > ").strip().lower() != "stop"


def run_rows(log_dir, last: int = 20) -> list[Text]:
    """One row per recent run: id, outcome in its tone, steps, task."""
    from pathlib import Path

    from casca.replay import load_run

    rows = []
    for path in sorted(Path(log_dir).glob("run_*"), reverse=True)[:last]:
        try:
            meta, steps = load_run(path)
        except (OSError, ValueError) as e:
            rows.append(Text(f"{path.name}  could not load: {e}", "ui_error"))
            continue
        outcome = meta.get("outcome", "unfinished")
        tone = "ui_ok" if outcome == "done" else "ui_error" if outcome in ("crashed", "model_error", "parse_error") else "ui_warn"
        rows.append(Text(f"{path.name}  ").append(f"{outcome:12}", tone).append(f" {len(steps):>3} steps  {meta['task']}"))
    return rows
