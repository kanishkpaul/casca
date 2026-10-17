"""The interactive TUI, `casca` with no arguments: the banner on the empty state, a log of tool
rows, a rail with the latest step, the prompt and the status bar, as design/system/TUI.md lays
out. Rows are drawn by the same LineUI a plain run uses, so both read alike."""
import os
import subprocess
import sys
import threading

from rich.text import Span, Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from casca import term
from casca.ui import VERBS, LineUI, detail, run_rows


class AppUI(LineUI):
    """LineUI drawing into the app, answering its questions from keys on the app's thread."""

    def __init__(self, app: "CascaApp"):
        super().__init__("always")
        self.app, self.answered, self.answer = app, threading.Event(), False

    def write(self, text: Text) -> None:
        self.app.call_from_thread(self.app.log_row, text)

    def _spin(self, verb: str | None) -> None:
        self.app.call_from_thread(self.app.set_activity, verb)

    def emit(self, event: str, **fields) -> None:
        if event == "start":  # the app's header already names the model and where it runs
            self.write(Text(f" {term.IDENTITY['glyph']} {term.IDENTITY['agent']} ", "bold response_border"))
        else:
            super().emit(event, **fields)
        self.app.call_from_thread(self.app.track, event, fields)

    def _ask(self, mode: str) -> bool:
        self.answered.clear()
        self.app.call_from_thread(self.app.set_mode, mode)
        self.answered.wait()
        return self.answer

    def approve(self, action: dict, reason: str, element: dict | None = None) -> bool:
        self.approve_box(action, reason, element)
        return self._ask("approve")

    def pause(self, reason: str) -> bool:
        self.pause_box(reason, "[enter] I'm done · [esc] stop")
        return self._ask("pause")


class CascaApp(App):
    TITLE = "casca"
    BINDINGS = [
        Binding("escape", "escape", "stop", priority=True),
        Binding("enter", "enter", show=False, priority=True),
        Binding("y", "answer(True)", show=False),
        Binding("n", "answer(False)", show=False),
        Binding("ctrl+t", "runs", "runs"),
        Binding("ctrl+o", "open_frame", "open frame"),
        Binding("ctrl+r", "rail", "rail"),
    ]

    def __init__(self, make_agent, model: str, locality: str, log_dir: str):
        p = term.PALETTES[term.polarity()]
        self.CSS = f"""
        Screen {{ background: {p['status_bar_bg']}; color: {p['banner_text']}; }}
        #log {{ border-right: solid {p['banner_border']}; padding: 0 1;
               scrollbar-background: {p['status_bar_bg']}; scrollbar-color: {p['session_border']}; }}
        #rail {{ width: 34; padding: 0 1; }}
        Input {{ border: tall {p['input_rule']}; background: {p['status_bar_bg']}; }}
        #status {{ height: 1; background: {p['completion_menu_bg']}; color: {p['status_bar_text']}; }}
        """
        super().__init__()
        self.make_agent, self.model, self.locality, self.log_dir = make_agent, model, locality, log_dir
        self.mode, self.agent, self.ui, self.step, self.sent, self.activity = "idle", None, None, 0, 0, None

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield RichLog(id="log", wrap=True)
            yield Static(id="rail")
        yield Input(placeholder="what should Casca do?", id="prompt")
        yield Static(id="status")

    def on_mount(self) -> None:
        log, identity = self.query_one("#log", RichLog), term.IDENTITY
        rows = identity["banner"].splitlines()
        if self.size.width >= max(map(len, rows)) + 4 + 34:
            for row, tone in zip(rows, ["banner_title"] * 2 + ["banner_accent"] * 2 + ["banner_border"] * 2):
                log.write(Text(row, self.style(tone)))
        else:
            log.write(Text(f"{identity['glyph']} {identity['name']}", self.style("banner_title")))
        log.write(Text(f"{identity['glyph']} casca · {self.model} · {self.locality}", self.style("banner_dim")))
        self.refresh_status()

    def style(self, name: str) -> str:
        return term.PALETTES[term.polarity()][name]

    def log_row(self, text: Text) -> None:
        # Rows carry theme style names; Textual's RichLog needs the colours themselves.
        palette = term.PALETTES[term.polarity()]
        colour = lambda style: " ".join(palette.get(part, part) for part in str(style).split())
        text.spans = [Span(s.start, s.end, colour(s.style)) for s in text.spans]
        text.style = colour(text.style) if text.style else ""
        self.query_one("#log", RichLog).write(text)

    def set_activity(self, verb: str | None) -> None:
        self.activity = verb
        self.refresh_status()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = mode != "idle"
        if mode == "idle":
            prompt.focus()
        self.refresh_status()

    def track(self, event: str, fields: dict) -> None:
        self.step = fields.get("step", self.step)
        if event == "act" and fields["action"]["action"] not in ("done", "fail", "handback"):
            action, result, element = fields["action"], fields["result"], fields.get("element") or {}
            lines = [(VERBS.get(action["action"], ("", action["action"]))[1], "banner_title"),
                     (f"target  {detail(action, element)}", None), (f"role    {element.get('role') or '-'}", None),
                     (f"app     {element.get('app') or '-'}", None), (f"expect  {action.get('expect', '-')}", None),
                     (f"result  {result.get('status')} {result.get('settle_s', '')}", None)]
            rail = Text()
            for line, tone in lines:
                rail.append(line + "\n", self.style(tone) if tone else "")
            self.query_one("#rail", Static).update(rail)
        if event == "end":
            self.sent += fields.get("sent_bytes", 0)
        self.refresh_status()

    def refresh_status(self) -> None:
        p = term.PALETTES[term.polarity()]
        parts = [(self.model, p["status_bar_strong"]), (f"step {self.step + 1}", None)]
        if self.size.width >= 60:  # narrow terminals keep the model, the step and anything waiting on you
            parts[1:1] = [(self.locality, None)]
            parts.append((f"{self.sent / 1000:.0f} KB sent", None))
        if self.mode == "approve":
            parts.append(("1 gate · y approve · n deny", p["status_bar_warn"]))
        elif self.mode == "pause":
            parts.append(("your turn · enter when done", p["status_bar_warn"]))
        elif self.activity:
            parts.append((f"{term.IDENTITY['glyph']} {self.activity}…", p["ui_accent"]))
        parts.append(("esc stop" if self.mode == "running" else "ctrl+t runs · ctrl+q quit", p["status_bar_dim"]))
        bar = Text(" ")
        for i, (text, color) in enumerate(parts):
            bar.append((" │ " if i else ""), p["status_bar_dim"]).append(text, color or "")
        self.query_one("#status", Static).update(bar)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        task = message.value.strip()
        if not task or self.mode != "idle":
            return
        message.input.value = ""
        self.log_row(Text("❯ ", "prompt").append(task))
        self.set_mode("running")
        self.ui = AppUI(self)
        threading.Thread(target=self._run, args=(task,), daemon=True).start()

    def _run(self, task: str) -> None:
        self.agent = self.make_agent(self.ui)
        self.agent.run(task)
        self.call_from_thread(self.set_mode, "idle")
        self.call_from_thread(self.set_activity, None)

    def _reply(self, value: bool) -> None:
        self.ui.answer = value
        self.set_mode("running")
        self.ui.answered.set()

    def action_answer(self, value: bool) -> None:
        if self.mode == "approve":
            self._reply(value)

    async def action_enter(self) -> None:
        if self.mode == "approve":
            self._reply(False)  # Enter alone never approves.
        elif self.mode == "pause":
            self._reply(True)
        else:
            await self.query_one("#prompt", Input).action_submit()

    def action_escape(self) -> None:
        if self.mode in ("approve", "pause"):
            self._reply(False)
        elif self.mode == "running" and getattr(self.agent, "stop_requested", None):
            self.agent.stop_requested.set()
            self.set_activity("stopping before the next act")

    def action_runs(self) -> None:
        if self.mode == "idle":
            for row in run_rows(self.log_dir, 10):
                self.log_row(row)

    def action_rail(self) -> None:
        rail = self.query_one("#rail", Static)
        rail.display = not rail.display

    def action_open_frame(self) -> None:
        if not (self.agent and getattr(self.agent, "logger", None)):
            return
        frames = sorted(self.agent.logger.screenshots_dir.glob("*.png"))
        if frames:
            if sys.platform == "win32":
                os.startfile(frames[-1])
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(frames[-1])], check=False)
