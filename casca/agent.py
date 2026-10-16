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

console = Console()

class CascaAgent:
    def __init__(
        self,
        model: VisionActionModel,
        max_steps: int = config.MAX_STEPS,
        step_delay: float = config.STEP_DELAY,
        unsafe: bool = False,
        confirm_each_step: bool = False,
        dry_run: bool = False,
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
        
        self.screen = screen or ScreenObserver()
        screen_size = self.screen.get_screen_size()
        self.desktop = desktop or DesktopController(screen_size["width"], screen_size["height"])
        self.safety = SafetyPolicy(unsafe=self.unsafe)
        self.log_dir = log_dir
        self.history = []

    def parse_action(self, raw_output: str) -> ActionType | None:
        try:
            # Simple extraction: find the first { and last }
            raw_output = raw_output or ""
            start = raw_output.find("{")
            end = raw_output.rfind("}")
            
            if start == -1 or end == -1:
                return None
                
            json_str = raw_output[start:end+1]
            data = json.loads(json_str)
            adapter = TypeAdapter(ActionType)
            return adapter.validate_python(data)
        except (json.JSONDecodeError, ValidationError) as e:
            console.print(f"[red]Error parsing action:[/red] {escape(str(e))}")
            return None

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
        screen_size = self.screen.get_screen_size()

        for step in range(self.max_steps):
            console.print(f"\n[cyan]=== Step {step} ===[/cyan]")
            screenshot = self.screen.screenshot()

            def log(action, safety, execution, raw=None):
                self.logger.log_step(step, task, screenshot, raw, action, safety, execution)

            console.print("[dim]Thinking...[/dim]")
            result = self.model.propose_action(task, screenshot, step, self.history, screen_size)

            if "error" in result:
                console.print(f"[bold red]Model error:[/bold red] {escape(str(result['error']))}")
                log(None, None, {"status": "model_error", "error": result["error"]})
                return "model_error"

            raw_output = result["raw_output"]
            action = self.parse_action(raw_output)

            if not action:
                console.print("[bold red]Failed to parse action. Stopping.[/bold red]")
                console.print(f"Raw output:\n{escape(str(raw_output))}")
                log(None, None, {"status": "parse_error"}, raw_output)
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
                confirm = console.input("[bold yellow]Execute this action? [y/N]: [/bold yellow]")
                if confirm.lower() != 'y':
                    console.print("[yellow]Action aborted by user. Stopping.[/yellow]")
                    log(action.model_dump(), safety_log, {"status": "aborted"}, raw_output)
                    return "aborted"

            if self.dry_run:
                console.print("[yellow][DRY RUN] Skipping execution[/yellow]")
                execution_log = {"status": "success"}
            else:
                console.print("[dim]Executing...[/dim]")
                try:
                    execution_log = self.desktop.execute_action(action)
                except FailSafeException:
                    log(action.model_dump(), safety_log, {"status": "interrupted"}, raw_output)
                    raise
                except Exception as e:
                    execution_log = {"status": "error", "error": f"{type(e).__name__}: {e}"}

            log(action.model_dump(), safety_log, execution_log, raw_output)
            self.history.append({"step": step, "action": action.action, "execution": execution_log})

            if action.action == "done":
                console.print(f"[bold green]Task completed![/bold green]\nAnswer: {escape(action.answer)}")
                return "done"
            if action.action == "fail":
                console.print(f"[bold red]Agent reported failure:[/bold red]\nReason: {escape(action.reason)}")
                return "fail"
            if execution_log["status"] != "success":
                console.print(f"[bold red]Execution failed:[/bold red] {escape(str(execution_log.get('error')))}")

            time.sleep(self.step_delay)

        console.print("[yellow]Reached maximum steps without completion.[/yellow]")
        return "max_steps"
