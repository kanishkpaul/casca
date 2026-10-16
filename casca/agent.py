import json
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

    def _settle(self, before: bytes, every: float = 0.15) -> dict:
        """Waits until the screen has changed and stopped changing, instead of a fixed sleep."""
        start, last = time.monotonic(), before
        while time.monotonic() - start < self.settle_timeout:
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
        try:
            outcome = self._loop(task)
        except (KeyboardInterrupt, FailSafeException):
            outcome = "interrupted"
            console.print("[yellow]Interrupted. Stopping.[/yellow]")
        finally:
            self.logger.finish(outcome)
        return outcome

    def _loop(self, task: str) -> str:
        monitor = self.screen.get_screen_size()
        if not self.dry_run and (problem := self.desktop.input_problem()):
            console.print(f"[bold red]Cannot send input:[/bold red] {problem}")
            return "no_input"

        started = time.monotonic()
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

            if self.confirm_each_step and not self.dry_run:
                confirm = console.input("[bold yellow]Execute this action? \\[y/N]: [/bold yellow]")
                if confirm.lower() != 'y':
                    console.print("[yellow]Action aborted by user. Stopping.[/yellow]")
                    log(action.model_dump(), safety_log, {"status": "aborted"}, raw_output)
                    return "aborted"

            if self.dry_run:
                console.print("[yellow][DRY RUN] Skipping execution[/yellow]")
                execution_log = {"status": "skipped"}
            else:
                console.print("[dim]Executing...[/dim]")
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
                console.print(f"[bold yellow]Your turn:[/bold yellow] {escape(action.reason)}")
                return "handed_back"
            if action.action == "fail":
                console.print(f"[bold red]Agent reported failure:[/bold red]\nReason: {escape(action.reason)}")
                return "fail"
            if execution_log["status"] not in ("success", "skipped"):
                console.print(f"[bold red]Execution failed:[/bold red] {escape(str(execution_log.get('error')))}")


        console.print("[yellow]Reached maximum steps without completion.[/yellow]")
        return "max_steps"
