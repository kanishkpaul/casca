import typer
from rich.console import Console
from rich.markup import escape
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
    coords: str = typer.Option(config.COORDS, "--coords", help="'image_px', or 'norm1000' for models such as Qwen3-VL."),
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
        coords=coords,
        log_dir=log_dir
    )
    
    agent.run(task)

@app.command()
def doctor(
    base_url: str = typer.Option(config.BASE_URL, "--base-url"),
    api_key: str = typer.Option(config.API_KEY or "", "--api-key", hidden=True),
):
    """Check capture, input, displays and the model endpoint. Moves the pointer once and back."""
    import platform
    import sys

    import httpx
    import pyautogui

    from casca.desktop import DesktopController
    from casca.screen import ScreenObserver

    screen = ScreenObserver()
    screen.screenshot()
    monitor = screen.get_screen_size()
    desktop = DesktopController(monitor["width"], monitor["height"])
    rows = [("os", None, f"{platform.system()} {platform.release()} · Python {platform.python_version()}"),
            ("displays", None, " · ".join(f"{m['width']}x{m['height']} at ({m['left']}, {m['top']})" for m in screen.sct.monitors[1:])),
            ("scale", None, f"monitor {screen.monitor_index}: capture {screen.capture_size[0]} px for {monitor['width']} points = {screen.capture_size[0] / monitor['width']:g}x"),
            ("screen", screen.capture_problem(), "captured"),
            ("input", desktop.input_problem(), "allowed")]
    start, centre = pyautogui.position(), (monitor["left"] + monitor["width"] // 2, monitor["top"] + monitor["height"] // 2)
    desktop.move_mouse(*centre)
    got = tuple(pyautogui.position())
    desktop.move_mouse(*start)
    rows.append(("pointer", None if got == centre else f"moved to {centre}, read back {got}", f"moved to {centre}, read back {got}"))
    rows.append(("console", None if (sys.stdout.encoding or "").lower().startswith("utf") else "not UTF-8; use Windows Terminal", sys.stdout.encoding))
    try:
        r = httpx.get(base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {api_key}"} if api_key else {}, timeout=5)
        rows.append(("model", None if r.status_code == 200 else f"{base_url} answered {r.status_code}", f"{base_url} answered 200"))
    except httpx.HTTPError as e:
        rows.append(("model", f"{base_url}: {type(e).__name__}", ""))
    for name, problem, detail in rows:
        mark = "[red]error[/red]" if problem else "[green]ok   [/green]"
        console.print(f"{mark} {name:9} {escape(problem or detail)}")
    failed = sum(1 for _, problem, _ in rows if problem)
    if failed:
        console.print(f"[red]{failed} check{'s' if failed > 1 else ''} failed.[/red]")
        raise typer.Exit(1)

@app.command()
def web(port: int = typer.Option(5000, "--port", help="Port on localhost.")):
    """Start the replay viewer for past runs."""
    from casca.web.app import app as viewer
    viewer.run(port=port)

if __name__ == "__main__":
    app()
