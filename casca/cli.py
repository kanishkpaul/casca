import typer
from rich.console import Console
from typing import Optional
from casca.agent import CascaAgent
from casca.models.hf_provider import HFVisionProvider
from casca.models.mock_provider import MockVisionProvider
from casca.config import config
import os
import subprocess
from pathlib import Path

app = typer.Typer(help="Casca: Screenshot-based desktop-control agent.")
console = Console()

@app.command()
def run(
    task: str = typer.Argument(..., help="The task for the agent to accomplish."),
    max_steps: int = typer.Option(config.MAX_STEPS, "--max-steps", help="Maximum number of steps."),
    provider: str = typer.Option("hf", "--provider", help="Model provider ('hf' or 'mock')."),
    unsafe: bool = typer.Option(False, "--unsafe", help="Allow potentially dangerous actions."),
    confirm_each_step: bool = typer.Option(False, "--confirm-each-step", help="Ask for confirmation before each action."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Propose actions without executing them."),
    log_dir: str = typer.Option(config.LOG_DIR, "--log-dir", help="Directory to save logs."),
):
    """Run the Casca agent on a specific task."""
    if provider == "mock":
        model = MockVisionProvider()
    elif provider == "hf":
        try:
            model = HFVisionProvider()
        except ValueError as e:
            console.print(f"[bold red]Configuration error:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        console.print(f"[bold red]Unknown provider:[/bold red] {provider}")
        raise typer.Exit(1)
        
    agent = CascaAgent(
        model=model,
        max_steps=max_steps,
        unsafe=unsafe,
        confirm_each_step=confirm_each_step,
        dry_run=dry_run,
        log_dir=log_dir
    )
    
    agent.run(task)

@app.command()
def web():
    """Start the built-in web UI to view runs and logs."""
    console.print("[green]Starting Casca Web UI...[/green]")
    # Get the path to the web folder
    pkg_dir = Path(__file__).parent.parent
    web_dir = pkg_dir / "web"
    app_path = web_dir / "app.py"
    
    env = os.environ.copy()
    env["FLASK_APP"] = str(app_path)
    env["FLASK_ENV"] = "development"
    
    subprocess.run(["flask", "run"], env=env)

if __name__ == "__main__":
    app()
