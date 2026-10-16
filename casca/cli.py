import typer
from rich.console import Console
from typing import Optional
from casca.agent import CascaAgent
from casca.models.openai_compat import OpenAICompatProvider
from casca.models.mock_provider import MockVisionProvider
from casca.config import config

app = typer.Typer(help="Casca: Screenshot-based desktop-control agent.")
console = Console()

@app.command()
def run(
    task: str = typer.Argument(..., help="The task for the agent to accomplish."),
    max_steps: int = typer.Option(config.MAX_STEPS, "--max-steps", help="Maximum number of steps."),
    provider: str = typer.Option("api", "--provider", help="'api' for any OpenAI-compatible endpoint, or 'mock'."),
    base_url: str = typer.Option(config.BASE_URL, "--base-url", help="Endpoint, e.g. http://localhost:11434/v1 for Ollama."),
    model_name: str = typer.Option(config.MODEL, "--model", help="Model name at that endpoint."),
    unsafe: bool = typer.Option(False, "--unsafe", help="Allow potentially dangerous actions."),
    confirm_each_step: bool = typer.Option(False, "--confirm-each-step", help="Ask for confirmation before each action."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Propose actions without executing them."),
    log_dir: str = typer.Option(config.LOG_DIR, "--log-dir", help="Directory to save logs."),
):
    """Run the Casca agent on a specific task."""
    if provider == "mock":
        model = MockVisionProvider()
    elif provider == "api":
        model = OpenAICompatProvider(base_url, model_name)
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
def web(port: int = typer.Option(5000, "--port", help="Port on localhost.")):
    """Start the replay viewer for past runs."""
    from casca.web.app import app as viewer
    viewer.run(port=port)

if __name__ == "__main__":
    app()
