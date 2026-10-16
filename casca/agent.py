import json
import sys
import threading
import time
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from pyautogui import FailSafeException
from pydantic import ValidationError, TypeAdapter

from casca.screen import ScreenObserver
from casca.desktop import DesktopController
from casca.logger import RunLogger
from casca.safety import SafetyPolicy
from casca.models.base import VisionActionModel
from casca.actions import ActionType
from casca.config import config
from casca import gates
from casca.coords import POINT_FIELDS, to_screen

console = Console()
ACTIONS = TypeAdapter(ActionType)
PARSE_ATTEMPTS = 3
STUCK_REPEATS = 3


def signature(action: dict) -> tuple:
    """An act with its target rounded to 10 px, so repeating "the same click" is detectable."""
    return tuple((k, v // 10 if k in POINT_FIELDS else v) for k, v in sorted(action.items())
                 if k not in ("reason", "expect", "previous"))

class CascaAgent:
    def __init__(
        self,
        model: VisionActionModel,
        max_steps: int = config.MAX_STEPS,
        max_seconds: float = config.MAX_SECONDS,
        settle_timeout: float = 2.0,
        unsafe: bool = False,
        confirm_each_step: bool = False,
        dry_run: bool = False,
        coords: str = config.COORDS,
        apps: list[str] | None = None,
        log_dir: str = config.LOG_DIR,
        screen=None,
        desktop=None,
    ):
        self.model = model
        self.max_steps = max_steps
        self.max_seconds = max_seconds
        self.settle_timeout = settle_timeout
        self.unsafe = unsafe
        self.confirm_each_step = confirm_each_step
        self.dry_run = dry_run
        self.coords = coords
        self.apps = apps or []
        
        self.screen = screen or ScreenObserver()
        screen_size = self.screen.get_screen_size()
        self.desktop = desktop or DesktopController(screen_size["width"], screen_size["height"])
        self.safety = SafetyPolicy(unsafe=self.unsafe)
        self.log_dir = log_dir
        self.history = []

    def parse_action(self, raw_output: str | None) -> tuple[ActionType | None, str | None]:
        """Reads the first JSON object in the reply. Returns the action, or None and why not."""
        text = raw_output or ""
        start = text.find("{")
        if start == -1:
            return None, "the reply has no JSON object"
        try:
            data, _ = json.JSONDecoder().raw_decode(text, start)
            return ACTIONS.validate_python(data), None
        except json.JSONDecodeError as e:
            return None, f"invalid JSON: {e}"
        except ValidationError as e:
            return None, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())

    def _gate(self, action, size, monitor) -> tuple[str, str | None, dict | None]:
        target = focused = None
        if action.action in gates.POINTER:
            try:
                mapped = to_screen(action, size, monitor)
            except ValueError:
                return "allow", None, None  # execution reports the point as outside the screenshot
            target = self.desktop.element_at(*((mapped.x, mapped.y) if hasattr(mapped, "x") else (mapped.x1, mapped.y1)))
        elif action.action in gates.KEYBOARD:
            focused = self.desktop.focused_element()
        decision, reason = gates.check(action, target, focused, self.apps)
        return decision, reason, target or focused

    def _approve(self, action, reason: str) -> bool:
        """Asks the user. Deny is the default, and a run with no terminal attached always denies."""
        if not sys.stdin.isatty():
            return False
        console.print(f"[yellow]╭─ approve? ─[/yellow]\n[yellow]│[/yellow] {action.action} {escape(action.reason)}\n"
                      f"[yellow]│[/yellow] [dim]{escape(reason)}[/dim]\n[yellow]╰─ \\[y] approve once · \\[n/enter] deny ─[/yellow]")
        return console.input("> ").strip().lower() == "y"

    @staticmethod
    def _moved(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return abs(a[0] - b[0]) > 5 or abs(a[1] - b[1]) > 5

    def _pause(self, reason: str) -> bool:
        """Hands control to the user. True to carry on from a fresh capture; no terminal means stop."""
        console.print(f"[bold yellow]Your turn:[/bold yellow] {escape(reason)}")
        if not sys.stdin.isatty():
            return False
        return console.input("Press Enter when done, or type stop: ").strip().lower() != "stop"

    def _watch_stop(self) -> None:
        while not self.finished.is_set():
            if self.desktop.stop_pressed():
                self.stop_requested.set()
                return
            time.sleep(0.05)

    def _settle(self, before: bytes, every: float = 0.15) -> dict:
        """Waits until the screen has changed and stopped changing, instead of a fixed sleep."""
        start, last = time.monotonic(), before
        while time.monotonic() - start < self.settle_timeout and not self.stop_requested.is_set():
            time.sleep(every)
            frame = self.screen.screenshot()
            if frame == last != before:
                break
            last = frame
        return {"settle_s": round(time.monotonic() - start, 2), "changed": last != before}

    def run(self, task: str) -> str:
        console.print(Panel(f"Starting Casca Agent\nTask: [bold]{escape(task)}[/bold]\nMax steps: {self.max_steps}"))

        is_safe, reason = self.safety.check_task(task)
        if not is_safe:
            console.print(f"[bold red]Task rejected by safety policy:[/bold red] {escape(str(reason))}")
            return "rejected"

        self.logger = RunLogger(log_dir=self.log_dir)
        self.logger.log_metadata(task, self.max_steps, self.model.__class__.__name__)
        outcome = "crashed"
        self.stop_requested, self.finished = threading.Event(), threading.Event()
        if not self.dry_run:
            threading.Thread(target=self._watch_stop, daemon=True).start()
        try:
            outcome = self._loop(task)
        except (KeyboardInterrupt, FailSafeException):
            outcome = "interrupted"
            console.print("[yellow]Interrupted. Stopping.[/yellow]")
        finally:
            self.finished.set()
            self.logger.finish(outcome)
        return outcome

    def _loop(self, task: str) -> str:
        monitor = self.screen.get_screen_size()
        if not self.dry_run and (problem := self.desktop.input_problem()):
            console.print(f"[bold red]Cannot send input:[/bold red] {problem}")
            return "no_input"

        started, self.left_at = time.monotonic(), None
        for step in range(self.max_steps):
            if time.monotonic() - started > self.max_seconds:
                console.print(f"[yellow]Stopped: the {self.max_seconds} s time budget is used up.[/yellow]")
                return "time_budget"
            console.print(f"\n[cyan]=== Step {step} ===[/cyan]")
            screenshot = self.screen.screenshot()
            width, height = (1000, 1000) if self.coords == "norm1000" else self.screen.image_size

            def log(action, safety, execution, raw=None):
                self.logger.log_step(step, task, screenshot, raw, action, safety, execution)

            # Checked every step: a frame that turns black mid-run can be the Windows UAC prompt,
            # which sits on a secure desktop Casca cannot capture or click.
            if problem := self.screen.capture_problem():
                console.print(f"[bold red]Cannot see the screen:[/bold red] {problem}")
                log(None, None, {"status": "blank_screen", "error": problem})
                return "blank_screen"

            console.print("[dim]Thinking...[/dim]")
            feedback = []
            for _ in range(PARSE_ATTEMPTS):
                result = self.model.propose_action(task, screenshot, step, self.history + feedback, {"width": width, "height": height})
                if "error" in result:
                    console.print(f"[bold red]Model error:[/bold red] {escape(str(result['error']))}")
                    log(None, None, {"status": "model_error", "error": result["error"]})
                    return "model_error"
                raw_output = result["raw_output"]
                action, problem = self.parse_action(raw_output)
                if action:
                    break
                console.print(f"[red]Invalid reply:[/red] {escape(problem)}")
                feedback = [{"step": step, "action": "invalid reply", "execution": {"status": "error", "error": problem}}]
            else:
                console.print(f"Raw output:\n{escape(str(raw_output))}")
                log(None, None, {"status": "parse_error", "error": problem}, raw_output)
                return "parse_error"

            console.print(f"[green]Proposed action:[/green] {action.action}")
            console.print(f"[green]Reason:[/green] {escape(action.reason)}")
            console.print(action.model_dump_json(indent=2), markup=False)

            action_is_safe, safety_reason = self.safety.check_action(action, task)
            safety_log = {"allowed": action_is_safe, "reason": safety_reason}

            if not action_is_safe:
                console.print(f"[bold red]Action blocked by safety policy:[/bold red] {escape(str(safety_reason))}")
                log(action.model_dump(), safety_log, {"status": "blocked"}, raw_output)
                return "blocked"

            decision, gate_reason, element = self._gate(action, (width, height), monitor)
            safety_log.update(gate=decision, gate_reason=gate_reason, element=element)
            refused = decision == "refuse" or (decision == "confirm" and not self.dry_run
                                               and not self._approve(action, gate_reason))

            if self.confirm_each_step and not self.dry_run:
                confirm = console.input("[bold yellow]Execute this action? \\[y/N]: [/bold yellow]")
                if confirm.lower() != 'y':
                    console.print("[yellow]Action aborted by user. Stopping.[/yellow]")
                    log(action.model_dump(), safety_log, {"status": "aborted"}, raw_output)
                    return "aborted"

            if refused:
                console.print(f"[bold yellow]Not done:[/bold yellow] {escape(gate_reason)}")
                execution_log = {"status": "refused", "error": gate_reason}
            elif self.dry_run:
                console.print("[yellow][DRY RUN] Skipping execution[/yellow]")
                execution_log = {"status": "skipped"}
            else:
                console.print("[dim]Executing...[/dim]")
                if self.stop_requested.is_set():
                    console.print("[bold yellow]Stopped by the stop keys.[/bold yellow] Nothing was undone.")
                    log(action.model_dump(), safety_log, {"status": "stopped"}, raw_output)
                    return "stopped"
                if self.left_at and self._moved(self.desktop.cursor(), self.left_at):
                    if not self._pause("you moved the mouse, so Casca paused."):
                        log(action.model_dump(), safety_log, {"status": "taken_over"}, raw_output)
                        return "taken_over"
                    self.left_at = None
                    continue
                if problem := self.desktop.input_problem():
                    console.print(f"[bold red]Cannot send input:[/bold red] {problem}")
                    log(action.model_dump(), safety_log, {"status": "no_input", "error": problem}, raw_output)
                    return "no_input"
                try:
                    execution_log = self.desktop.execute_action(to_screen(action, (width, height), monitor))
                except FailSafeException:
                    log(action.model_dump(), safety_log, {"status": "interrupted"}, raw_output)
                    raise
                except Exception as e:
                    execution_log = {"status": "error", "error": f"{type(e).__name__}: {e}"}

            if execution_log["status"] == "success" and action.action not in ("done", "fail", "handback", "wait"):
                execution_log.update(self._settle(screenshot))
            if execution_log["status"] == "success" and action.action in gates.POINTER | {"move_mouse"}:
                self.left_at = self.desktop.cursor()
            if action.previous and self.history:
                self.history[-1]["verified"] = action.previous
            log(action.model_dump(), safety_log, execution_log, raw_output)
            self.history.append({"step": step, "action": action.model_dump(), "execution": execution_log})
            recent = [signature(h["action"]) for h in self.history[-STUCK_REPEATS:] if isinstance(h["action"], dict)]
            if len(recent) == STUCK_REPEATS and len(set(recent)) == 1 and action.action not in ("wait", "done"):
                console.print(f"[bold red]Stopped:[/bold red] the same {action.action} {STUCK_REPEATS} times in a row.")
                return "stuck"

            if action.action == "done":
                console.print(f"[bold green]Task completed![/bold green]\nAnswer: {escape(action.answer)}")
                return "done"
            if action.action == "handback":
                if self.dry_run or not self._pause(action.reason):
                    return "handed_back"
                self.history[-1]["execution"] = {"status": "user_done", "note": "the user finished this and said to carry on"}
                continue
            if action.action == "fail":
                console.print(f"[bold red]Agent reported failure:[/bold red]\nReason: {escape(action.reason)}")
                return "fail"
            if execution_log["status"] not in ("success", "skipped"):
                console.print(f"[bold red]Execution failed:[/bold red] {escape(str(execution_log.get('error')))}")


        console.print("[yellow]Reached maximum steps without completion.[/yellow]")
        return "max_steps"
