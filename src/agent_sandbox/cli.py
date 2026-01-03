"""CLI for agent-sandbox."""

import sys
from collections import deque
from pathlib import Path

import click
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .config import get_default_shell
from .init import create_devcontainer, find_git_root
from .manager import SandboxManager
from .utils import find_project_root


console = Console()

# Number of build log lines to display
BUILD_LOG_LINES = 10


def get_manager(auto_init: bool = False) -> SandboxManager:
    """Get a SandboxManager instance, handling errors gracefully.

    Args:
        auto_init: If True, prompt to initialize devcontainer if not found.
    """
    try:
        return SandboxManager()
    except ValueError as e:
        if auto_init and "Could not find devcontainer.json" in str(e):
            # Offer to initialize
            git_root = find_git_root()
            if git_root:
                console.print(
                    f"[yellow]No devcontainer.json found in {git_root}[/yellow]"
                )
                if click.confirm("Would you like to create one?", default=True):
                    create_devcontainer(git_root)
                    console.print(
                        "[green]Created .devcontainer/devcontainer.json[/green]"
                    )
                    console.print()
                    return SandboxManager()

        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@click.group()
@click.version_option()
def main():
    """agent-sandbox: Create sandboxed development environments using git worktrees and Docker."""
    pass


@main.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    help="Project path (default: current directory)",
)
def init(path: str | None):
    """Initialize a devcontainer configuration for agent-sandbox."""
    project_path = Path(path) if path else Path.cwd()

    # Check if we're in a git repo
    git_root = find_git_root(project_path)
    if not git_root:
        console.print(
            "[red]Error:[/red] Not in a git repository. Please initialize git first."
        )
        sys.exit(1)

    # Check if devcontainer already exists
    if find_project_root(project_path):
        console.print("[yellow]devcontainer.json already exists.[/yellow]")
        if not click.confirm("Overwrite?", default=False):
            return

    create_devcontainer(git_root)

    console.print()
    console.print(
        f"[green]Created .devcontainer/devcontainer.json in {git_root}[/green]"
    )
    console.print()
    console.print("You can now connect to a sandbox with:")
    console.print("  [cyan]agent-sandbox connect <name>[/cyan]")


@main.command()
@click.argument("name")
def stop(name: str):
    """Stop a sandbox."""
    manager = get_manager()

    with console.status(f"[bold blue]Stopping sandbox '{name}'...", spinner="dots"):
        manager.stop(name)
    console.print(f"[green]Sandbox '{name}' stopped.[/green]")


@main.command()
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Stop sandboxes from all projects (default: only current project)",
)
def stopall(all: bool):
    """Stop all running sandboxes."""
    manager = get_manager()

    with console.status("[bold blue]Stopping all sandboxes...", spinner="dots"):
        stopped = manager.stop_all(all_namespaces=all)

    if stopped:
        for name in stopped:
            console.print(f"  [dim]Stopped:[/dim] {name}")
        console.print("[green]All sandboxes stopped.[/green]")
    else:
        if all:
            console.print("No sandboxes were running.")
        else:
            console.print("No sandboxes were running for this project.")
            console.print("Use --all to stop sandboxes from all projects.")


@main.command()
@click.argument("name")
def rm(name: str):
    """Remove a sandbox and its clone."""
    manager = get_manager()

    with console.status(f"[bold blue]Removing sandbox '{name}'...", spinner="dots"):
        manager.remove(name)
    console.print(f"[green]Sandbox '{name}' removed.[/green]")


@main.command("ps")
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="List sandboxes from all projects (default: only current project)",
)
def list_sandboxes(all: bool):
    """List all running sandboxes."""
    manager = get_manager()

    sandboxes = manager.list(all_namespaces=all)

    if not sandboxes:
        if all:
            console.print("No sandboxes running.")
        else:
            console.print("No sandboxes running for this project.")
            console.print("Use --all to see sandboxes from all projects.")
        return

    title = (
        "Running Sandboxes"
        if all
        else f"Running Sandboxes ({manager._docker.namespace})"
    )
    table = Table(title=title)
    table.add_column("Name", style="cyan")
    table.add_column("Branch", style="green")
    table.add_column("Ports", style="yellow")

    for sandbox in sandboxes:
        ports_str = ", ".join(f"{cp}:{hp}" for cp, hp in sandbox.ports.items())
        table.add_row(sandbox.name, sandbox.branch, ports_str)

    console.print(table)


@main.command()
@click.argument("name")
@click.option(
    "--shell",
    "-s",
    default=None,
    help="Shell to use (default: from config or /bin/bash)",
)
@click.option(
    "--branch", "-b", help="Branch to use if starting (default: sandbox/<name>)"
)
@click.option("--yes", "-y", is_flag=True, help="Start sandbox without prompting")
def connect(name: str, shell: str | None, branch: str | None, yes: bool):
    """Connect to a sandbox's shell. Starts the sandbox if not running."""
    manager = get_manager(auto_init=True)

    # Check if sandbox is running, if not offer to start it
    if not manager._docker.container_exists(name):
        if not yes and not click.confirm(
            f"Sandbox '{name}' is not running. Start it?", default=True
        ):
            return

        try:
            # State for the live display
            current_status = "Starting sandbox..."
            build_lines: deque[str] = deque(maxlen=BUILD_LOG_LINES)

            def make_display() -> Group:
                """Create the live display content."""
                items = []
                # Spinner with current status
                items.append(Spinner("dots", text=f"[bold blue]{current_status}"))
                # Build log panel if we have output
                if build_lines:
                    log_text = Text("\n".join(build_lines), style="dim")
                    items.append(Panel(log_text, title="Build Output", border_style="blue"))
                return Group(*items)

            def on_progress(step: str) -> None:
                nonlocal current_status
                current_status = step

            def on_build_output(line: str) -> None:
                build_lines.append(line)
                live.update(make_display())

            with Live(make_display(), console=console, refresh_per_second=10) as live:
                info = manager.start(
                    name,
                    branch,
                    on_progress=on_progress,
                    on_build_output=on_build_output,
                )
                # Update display one more time in case of final status
                live.update(make_display())

            console.print(f"[green]Sandbox '{name}' started![/green]")
            console.print(f"  [dim]Path:[/dim]    {info.sandbox_path}")
            console.print(f"  [dim]Branch:[/dim]  {info.branch}")
            console.print()

        except Exception as e:
            console.print(f"[red]Error starting sandbox:[/red] {e}")
            sys.exit(1)

    # Determine which shell to use
    actual_shell = shell or get_default_shell() or "/bin/bash"
    shell_name = actual_shell.split("/")[-1]  # Extract 'bash' from '/bin/bash'
    console.print(f"Connecting to sandbox '{name}' with {shell_name}...")

    try:
        manager.connect(name, actual_shell)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name")
def ports(name: str):
    """Show ports for a sandbox."""
    manager = get_manager()

    port_map = manager.ports(name)

    if not port_map:
        console.print(f"No ports found for sandbox '{name}' (not running?)")
        return

    console.print(f"[bold]Ports for '{name}':[/bold]")
    for container_port, host_port in port_map.items():
        console.print(f"  {container_port}/tcp -> 0.0.0.0:{host_port}")


@main.command()
@click.argument("name")
def logs(name: str):
    """Show logs for a sandbox."""
    manager = get_manager()
    manager.logs(name)


@main.command()
@click.argument("name")
def merge(name: str):
    """Merge a sandbox's changes into the current branch.

    This fetches the sandbox branch from the git server and merges it
    into your current branch. The sandbox must have pushed its changes
    first (git push origin sandbox/<name>).
    """
    manager = get_manager()

    with console.status(f"[bold blue]Merging sandbox '{name}'...", spinner="dots"):
        success, message = manager.merge(name)

    if success:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[yellow]{message}[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
