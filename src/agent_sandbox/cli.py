"""CLI for agent-sandbox."""

import sys

import click
from rich.console import Console
from rich.table import Table

from .manager import SandboxManager


console = Console()


def get_manager() -> SandboxManager:
    """Get a SandboxManager instance, handling errors gracefully."""
    try:
        return SandboxManager()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@click.group()
@click.version_option()
def main():
    """agent-sandbox: Create sandboxed development environments using git worktrees and Docker."""
    pass


@main.command()
@click.argument("name")
@click.option("--branch", "-b", help="Branch to use (default: sandbox/<name>)")
def start(name: str, branch: str | None):
    """Start a new sandbox with its own git worktree."""
    manager = get_manager()
    
    try:
        info = manager.start(name, branch)
        
        console.print()
        console.print(f"[green]Sandbox '{name}' started![/green]")
        console.print()
        console.print(f"  [bold]Worktree:[/bold]  {info.worktree_path}")
        console.print(f"  [bold]Branch:[/bold]    {info.branch}")
        
        if info.ports:
            console.print(f"  [bold]Ports:[/bold]")
            for container_port, host_port in info.ports.items():
                console.print(f"             {container_port} -> {host_port}")
        
        console.print()
        console.print(f"Connect with: [cyan]agent-sandbox connect {name}[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error starting sandbox:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name")
def stop(name: str):
    """Stop a sandbox."""
    manager = get_manager()
    
    console.print(f"Stopping sandbox '{name}'...")
    manager.stop(name)
    console.print(f"[green]Sandbox '{name}' stopped.[/green]")


@main.command()
def stopall():
    """Stop all running sandboxes."""
    manager = get_manager()
    
    console.print("Stopping all sandboxes...")
    stopped = manager.stop_all()
    
    if stopped:
        for name in stopped:
            console.print(f"  Stopped: {name}")
        console.print(f"[green]All sandboxes stopped.[/green]")
    else:
        console.print("No sandboxes were running.")


@main.command()
@click.argument("name")
def rm(name: str):
    """Remove a sandbox and its worktree."""
    manager = get_manager()
    
    console.print(f"Removing sandbox '{name}'...")
    manager.remove(name)
    console.print(f"[green]Sandbox '{name}' removed.[/green]")


@main.command("list")
def list_sandboxes():
    """List all running sandboxes."""
    manager = get_manager()
    
    sandboxes = manager.list()
    
    if not sandboxes:
        console.print("No sandboxes running.")
        return
    
    table = Table(title="Running Sandboxes")
    table.add_column("Name", style="cyan")
    table.add_column("Branch", style="green")
    table.add_column("Ports", style="yellow")
    
    for sandbox in sandboxes:
        ports_str = ", ".join(
            f"{cp}:{hp}" for cp, hp in sandbox.ports.items()
        )
        table.add_row(sandbox.name, sandbox.branch, ports_str)
    
    console.print(table)


@main.command()
@click.argument("name")
@click.option("--shell", "-s", default="sh", help="Shell to use (default: sh)")
def connect(name: str, shell: str):
    """Connect to a sandbox's shell."""
    manager = get_manager()
    
    console.print(f"Connecting to sandbox '{name}' with {shell}...")
    manager.connect(name, shell)


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


if __name__ == "__main__":
    main()
