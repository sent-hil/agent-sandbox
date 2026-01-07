"""CLI for agent-sandbox."""

import os
import subprocess
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
from .utils import find_project_root, generate_sandbox_name


console = Console()

# Number of build log lines to display
BUILD_LOG_LINES = 10


def complete_sandbox_names(ctx, param, incomplete):
    """Complete sandbox names from running containers and filesystem."""
    try:
        # Check if -a/--all flag is set
        all_namespaces = ctx.params.get("all", False)

        # Get sandbox names from running containers
        manager = get_manager()
        running_sandboxes = []
        try:
            sandboxes = manager.list(all_namespaces=all_namespaces)
            running_sandboxes = [sandbox.name for sandbox in sandboxes]
        except (ValueError, RuntimeError):
            # If manager initialization fails, continue with filesystem only
            pass

        # Get sandbox names from filesystem (.sandboxes directory)
        # Only include filesystem sandboxes when showing current project only
        filesystem_sandboxes = []
        if not all_namespaces:
            try:
                project_root = find_project_root()
                if project_root:
                    sandboxes_dir = project_root / ".sandboxes"
                    if sandboxes_dir.exists():
                        filesystem_sandboxes = [
                            d.name for d in sandboxes_dir.iterdir() if d.is_dir()
                        ]
            except Exception:
                # If we can't find project root, continue with running sandboxes only
                pass

        # Merge: running sandboxes first (in order from ps), then filesystem sandboxes
        # Deduplicate while preserving order
        all_names = list(dict.fromkeys(running_sandboxes + filesystem_sandboxes))

        # Filter by incomplete prefix
        matches = [name for name in all_names if name.startswith(incomplete)]

        return matches
    except Exception:
        # If anything fails, return empty list to avoid breaking completion
        return []


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
@click.argument("name", shell_complete=complete_sandbox_names)
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
            console.print("Use -a to stop sandboxes from all projects.")


@main.command()
@click.argument("name", shell_complete=complete_sandbox_names)
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
            console.print("Use -a to see sandboxes from all projects.")
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
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Show sandboxes from all projects in autocomplete",
)
@click.argument("name", required=False, shell_complete=complete_sandbox_names)
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
def connect(
    all: bool, name: str | None, shell: str | None, branch: str | None, yes: bool
):
    """Connect to a sandbox's shell. Starts the sandbox if not running."""
    if name is None:
        project_root = find_project_root()
        if not project_root:
            console.print("[red]Error: Not in a project with devcontainer.json[/red]")
            sys.exit(1)

        sandboxes_dir = project_root / ".sandboxes"
        name = generate_sandbox_name(sandboxes_dir)
        console.print(f"Generated sandbox name: [cyan]{name}[/cyan]")

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
                    items.append(
                        Panel(log_text, title="Build Output", border_style="blue")
                    )
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
@click.argument("name", shell_complete=complete_sandbox_names)
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
@click.argument("name", shell_complete=complete_sandbox_names)
def logs(name: str):
    """Show logs for a sandbox."""
    manager = get_manager()
    manager.logs(name)


@main.command()
@click.argument("name", shell_complete=complete_sandbox_names)
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


def _detect_shell() -> str | None:
    """Auto-detect current shell from environment."""
    shell_path = os.environ.get("SHELL", "")
    if "bash" in shell_path:
        return "bash"
    elif "zsh" in shell_path:
        return "zsh"
    elif "fish" in shell_path:
        return "fish"
    return None


def _get_program_name() -> str:
    """Get the program name for completion environment variable."""
    return "AGENT_SANDBOX"


def _generate_completion_instructions(shell: str, program_name: str) -> str:
    """Generate shell-specific installation instructions."""

    instructions = {
        "bash": f"""
[Bash Completion]

Add this to your ~/.bashrc:
    eval "$(_{program_name}_COMPLETE=bash_source agent-sandbox)"

Or save the script and source it:
    _{program_name}_COMPLETE=bash_source agent-sandbox > ~/.agent-sandbox-complete.bash
    echo 'source ~/.agent-sandbox-complete.bash' >> ~/.bashrc

Then restart your shell or run: source ~/.bashrc
        """.strip(),
        "zsh": f"""
[Zsh Completion]

Add this to your ~/.zshrc:
    eval "$(_{program_name}_COMPLETE=zsh_source agent-sandbox)"

Or save to completion directory:
    mkdir -p ~/.zfunc
    _{program_name}_COMPLETE=zsh_source agent-sandbox > ~/.zfunc/_agent-sandbox
    echo 'fpath+=~/.zfunc' >> ~/.zshrc
    echo 'autoload -U compinit && compinit' >> ~/.zshrc

Then restart your shell or run: source ~/.zshrc
        """.strip(),
        "fish": f"""
[Fish Completion]

Save this script:
    _{program_name}_COMPLETE=fish_source agent-sandbox > ~/.config/fish/completions/agent-sandbox.fish

Then restart fish or run:
    source ~/.config/fish/completions/agent-sandbox.fish
        """.strip(),
    }

    return instructions.get(shell, f"Shell '{shell}' is not supported.")


def _install_completion_script(shell: str, program_name: str) -> None:
    """Install completion script to appropriate location."""
    home = Path.home()

    # Define installation paths
    install_paths = {
        "bash": home / ".bash_completion.d" / "agent-sandbox.bash",
        "zsh": home / ".zfunc" / "_agent-sandbox",
        "fish": home / ".config" / "fish" / "completions" / "agent-sandbox.fish",
    }

    script_path = install_paths[shell]

    # Check if directory exists and is writable
    if not script_path.parent.exists():
        try:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created directory:[/green] {script_path.parent}")
        except PermissionError:
            console.print(f"[red]Error:[/red] Cannot create {script_path.parent}")
            console.print(
                "[yellow]Try running with sudo or use manual installation:[/yellow]"
            )
            console.print(_generate_completion_instructions(shell, program_name))
            return

    # Generate the completion script using Click's built-in system
    env_var = f"_{program_name}_COMPLETE={shell}_source"

    try:
        result = subprocess.run(
            ["agent-sandbox"],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, env_var: f"{shell}_source"},
        )
        script_path.write_text(result.stdout)

        console.print(f"[green]✓[/green] Installed {shell} completion to:")
        console.print(f"  [dim]{script_path}[/dim]")

        # Provide shell-specific next steps
        _print_post_install_instructions(shell)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error:[/red] Failed to generate completion script: {e}")
    except PermissionError:
        console.print(f"[red]Error:[/red] Cannot write to {script_path}")
        console.print(
            "[yellow]Try running with sudo or use manual installation:[/yellow]"
        )
        console.print(_generate_completion_instructions(shell, program_name))


def _print_post_install_instructions(shell: str) -> None:
    """Print shell-specific post-installation instructions."""

    instructions = {
        "bash": "[yellow]Restart your shell or run:[/yellow] source ~/.bashrc",
        "zsh": "[yellow]Restart your shell or run:[/yellow] source ~/.zshrc",
        "fish": "[yellow]Restart fish or run:[/yellow] source ~/.config/fish/completions/agent-sandbox.fish",
    }

    console.print(instructions.get(shell, "Restart your shell to enable completion."))


def _validate_shell_requirements(shell: str) -> None:
    """Validate shell version requirements and provide helpful warnings."""

    if shell == "bash":
        try:
            result = subprocess.run(
                ["bash", "--version"], capture_output=True, text=True
            )
            version_str = result.stdout.split()[2] if result.stdout else ""
            version_parts = version_str.split(".")
            if len(version_parts) >= 2:
                major, minor = int(version_parts[0]), int(version_parts[1])
                if major < 4 or (major == 4 and minor < 4):
                    console.print(
                        f"[yellow]Warning:[/yellow] Bash completion requires version 4.4+. "
                        f"Found: {major}.{minor}"
                    )
        except (subprocess.SubprocessError, IndexError, ValueError):
            console.print("[yellow]Warning:[/yellow] Could not detect bash version")


@main.command()
@click.argument("shell", required=False, type=click.Choice(["bash", "zsh", "fish"]))
@click.option(
    "--install",
    is_flag=True,
    help="Install completion script to the appropriate location",
)
def completion(shell: str | None, install: bool):
    """Generate shell completion for agent-sandbox.

    SHELL: Shell type (bash, zsh, fish). Auto-detected if not provided.

    Examples:
        agent-sandbox completion              # Auto-detect shell and show instructions
        agent-sandbox completion bash          # Show bash installation instructions
        agent-sandbox completion fish --install # Auto-install fish completion
    """
    program_name = _get_program_name()

    # Auto-detect shell if not provided
    if not shell:
        shell = _detect_shell()
        if not shell:
            console.print("[red]Error:[/red] Could not detect shell.")
            console.print("Please specify a shell: bash, zsh, or fish")
            sys.exit(1)
        console.print(f"[dim]Detected shell:[/dim] {shell}")

    # Validate shell requirements
    _validate_shell_requirements(shell)

    if install:
        _install_completion_script(shell, program_name)
    else:
        instructions = _generate_completion_instructions(shell, program_name)
        console.print(instructions)
        console.print()
        console.print(
            "[dim]Tip:[/dim] Use --install to automatically install the completion script"
        )


if __name__ == "__main__":
    main()
