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
from casca.coords import to_screen

console = Console()
ACTIONS = TypeAdapter(ActionType)
PARSE_ATTEMPTS = 3

class CascaAgent:
    def __init__(
        self,
        model: VisionActionModel,
        max_steps: int = config.MAX_STEPS,
        step_delay: float = config.STEP_DELAY,
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
        self.step_delay = step_delay
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

        for step in range(self.max_steps):
            console.print(f"\n[cyan]=== Step {step} ===[/cyan]")
            screenshot = self.screen.screenshot()
            width, height = (1000, 1000) if self.coords == "norm1000" else self.screen.image_size

            def log(action, safety, execution, raw=None):
                self.logger.log_step(step, task, screenshot, raw, action, safety, execution)

            if step == 0 and (problem := self.screen.capture_problem()):
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
                try:
                    execution_log = self.desktop.execute_action(to_screen(action, (width, height), monitor))
                except FailSafeException:
                    log(action.model_dump(), safety_log, {"status": "interrupted"}, raw_output)
                    raise
                except Exception as e:
                    execution_log = {"status": "error", "error": f"{type(e).__name__}: {e}"}

            log(action.model_dump(), safety_log, execution_log, raw_output)
            self.history.append({"step": step, "action": action.model_dump(), "execution": execution_log})

            if action.action == "done":
                console.print(f"[bold green]Task completed![/bold green]\nAnswer: {escape(action.answer)}")
                return "done"
            if action.action == "fail":
                console.print(f"[bold red]Agent reported failure:[/bold red]\nReason: {escape(action.reason)}")
                return "fail"
            if execution_log["status"] not in ("success", "skipped"):
                console.print(f"[bold red]Execution failed:[/bold red] {escape(str(execution_log.get('error')))}")

            time.sleep(self.step_delay)

        console.print("[yellow]Reached maximum steps without completion.[/yellow]")
        return "max_steps"
