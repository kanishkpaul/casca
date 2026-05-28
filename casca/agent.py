import json
import time
from rich.console import Console
from rich.panel import Panel
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
        log_dir: str = config.LOG_DIR
    ):
        self.model = model
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.unsafe = unsafe
        self.confirm_each_step = confirm_each_step
        self.dry_run = dry_run
        
        self.screen = ScreenObserver()
        screen_size = self.screen.get_screen_size()
        self.desktop = DesktopController(screen_size["width"], screen_size["height"])
        self.safety = SafetyPolicy(unsafe=self.unsafe)
        self.logger = RunLogger(log_dir=log_dir)
        self.history = []

    def parse_action(self, raw_output: str) -> ActionType | None:
        try:
            # Simple extraction: find the first { and last }
            start = raw_output.find("{")
            end = raw_output.rfind("}")
            
            if start == -1 or end == -1:
                return None
                
            json_str = raw_output[start:end+1]
            data = json.loads(json_str)
            adapter = TypeAdapter(ActionType)
            return adapter.validate_python(data)
        except (json.JSONDecodeError, ValidationError) as e:
            console.print(f"[red]Error parsing action:[/red] {e}")
            return None

    def run(self, task: str):
        console.print(Panel(f"Starting Casca Agent\nTask: [bold]{task}[/bold]\nMax steps: {self.max_steps}"))
        
        is_safe, reason = self.safety.check_task(task)
        if not is_safe:
            console.print(f"[bold red]Task rejected by safety policy:[/bold red] {reason}")
            return

        self.logger.log_metadata(task, self.max_steps, self.model.__class__.__name__)

        screen_size = self.screen.get_screen_size()

        for step in range(self.max_steps):
            console.print(f"\n[cyan]=== Step {step} ===[/cyan]")
            
            screenshot = self.screen.screenshot()
            
            console.print("[dim]Thinking...[/dim]")
            result = self.model.propose_action(task, screenshot, step, self.history, screen_size)
            
            if "error" in result:
                console.print(f"[bold red]Model error:[/bold red] {result['error']}")
                break
                
            raw_output = result["raw_output"]
            action = self.parse_action(raw_output)
            
            if not action:
                console.print("[bold red]Failed to parse action. Stopping.[/bold red]")
                console.print(f"Raw output:\n{raw_output}")
                break

            console.print(f"[green]Proposed action:[/green] {action.action}")
            console.print(f"[green]Reason:[/green] {action.reason}")
            console.print(action.model_dump_json(indent=2))

            action_is_safe, safety_reason = self.safety.check_action(action, task)
            safety_log = {"allowed": action_is_safe, "reason": safety_reason}
            
            if not action_is_safe:
                console.print(f"[bold red]Action blocked by safety policy:[/bold red] {safety_reason}")
                self.logger.log_step(step, task, screenshot, raw_output, action.model_dump(), safety_log, {"status": "blocked"})
                break

            if self.confirm_each_step and not self.dry_run:
                confirm = console.input("[bold yellow]Execute this action? [y/N]: [/bold yellow]")
                if confirm.lower() != 'y':
                    console.print("[yellow]Action aborted by user. Stopping.[/yellow]")
                    break

            execution_log = {"status": "success"}
            
            if not self.dry_run:
                console.print("[dim]Executing...[/dim]")
                execution_log = self.desktop.execute_action(action)
            else:
                console.print("[yellow][DRY RUN] Skipping execution[/yellow]")
                
            self.logger.log_step(step, task, screenshot, raw_output, action.model_dump(), safety_log, execution_log)
            
            self.history.append({
                "step": step,
                "action": action.action,
                "execution": execution_log
            })

            if action.action == "done":
                console.print(f"[bold green]Task completed![/bold green]\nAnswer: {action.answer}")
                break
            elif action.action == "fail":
                console.print(f"[bold red]Agent reported failure:[/bold red]\nReason: {action.reason}")
                break
                
            if execution_log.get("status") != "success":
                console.print(f"[bold red]Execution failed:[/bold red] {execution_log.get('error')}")
                
            time.sleep(self.step_delay)
            
        else:
            console.print("[yellow]Reached maximum steps without completion.[/yellow]")
