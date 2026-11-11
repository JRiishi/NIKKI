import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

# Ensure workspace in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.orchestrator.orchestrator import AgentOrchestrator
from src.service.model_service import LocalModelService
from src.gateway.interactive_session import InteractiveSession
from src.adapters.ollama_adapter import ensure_ollama_running

console = Console()

def print_health_dashboard(service: LocalModelService):
    console.print(Panel.fit("[bold green]Local AI Agent — Infrastructure Health Check[/bold green]"))
    hc = service.health_check()
    table = Table(title="Model Runtimes")
    table.add_column("Model / Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    for name, data in hc["models"].items():
        st = data.get("status", "unknown")
        det = f"Loaded: {data.get('loaded')} | Latency: {data.get('inference_latency_ms', 'N/A')}ms"
        table.add_row(name, st, det)

    console.print(table)
    console.print(f"[bold cyan]VRAM:[/bold cyan] {hc['vram']['used_mb']} MB used / {hc['vram']['total_mb']} MB total ({hc['vram']['utilization_pct']}%)")
    console.print(f"[bold cyan]Offline Mode:[/bold cyan] {hc['offline_mode']}")

def run_interactive_chat(service: LocalModelService, session_id: str = None):
    """
    Interactive discovery & planning REPL.
    Engages in dialogue to refine requirements, synthesize architecture,
    and requires explicit developer approval before initiating autonomous execution.
    """
    banner = (
        "[bold cyan]Welcome to Niiki — Autonomous Local AI Software Engineer[/bold cyan]\n\n"
        "• Chat freely about your project, architecture, dependencies, and requirements.\n"
        "• We will refine the design until you are satisfied.\n"
        "• Once ready, give [bold green]one approval[/bold green] (type [bold green]'approve'[/bold green] or [bold green]'start'[/bold green]) to begin autonomous execution.\n"
        "• Type [bold yellow]'health'[/bold yellow] to check runtime status, or [bold red]'exit'[/bold red] to quit."
    )
    console.print(Panel(banner, title="Interactive Engineering Studio", border_style="cyan"))

    session = InteractiveSession(model_service=service, session_id=session_id)
    orchestrator = AgentOrchestrator(model_service=service)

    while True:
        try:
            user_input = console.input("\n[bold green]You >>> [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session exited. Goodbye![/yellow]")
            break

        if not user_input:
            continue

        lower_input = user_input.lower()
        if lower_input in ("exit", "quit", "q"):
            console.print("[yellow]Exiting engineering session. Goodbye![/yellow]")
            break

        if lower_input in ("health", "--health"):
            print_health_dashboard(service)
            continue

        if lower_input in ("clear", "cls"):
            console.clear()
            continue

        # Process user message through conversational discovery engine
        with console.status("[bold cyan]Niiki is thinking...[/bold cyan]"):
            reply, approved_goal = session.handle_message(user_input)

        if approved_goal is not None:
            # Plan approved! Launch the autonomous execution pipeline
            console.print(Panel(
                f"[bold green]✓ Plan Approved! Starting autonomous execution...[/bold green]\n\n"
                f"[dim]Goal: {approved_goal[:200]}...[/dim]",
                title="Execution Approved",
                border_style="green"
            ))

            result = orchestrator.run(approved_goal, session_id=session.session_id)

            # Update chat context with real execution outcome
            session.record_execution_result(
                status=result.status,
                tasks_completed=result.tasks_completed,
                total_tasks=result.tasks_completed + result.tasks_failed,
                feedback=result.verification.feedback if result.verification else "",
                files=result.verification.files_inspected if result.verification else []
            )

            console.print("\n" + result.final_response)
            console.print(Panel(
                "[bold cyan]Autonomous execution completed![/bold cyan]\n"
                "You can inspect the generated files, test results, or continue chatting to request modifications.",
                border_style="cyan"
            ))
        else:
            # Display conversational response
            console.print("\n[bold cyan]Niiki:[/bold cyan]")
            console.print(Markdown(reply))

def run_cli():
    parser = argparse.ArgumentParser(description="Autonomous Software Engineering Agent (Local Multi-Model)")
    parser.add_argument("prompt", nargs="*", help="Goal or task description for the agent.")
    parser.add_argument("--session", "-s", type=str, default=None, help="Session ID to create or resume.")
    parser.add_argument("--health", action="store_true", help="Check local models and runtime health.")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve execution without interactive confirmation.")
    args = parser.parse_args()

    # Proactively ensure Ollama is available
    ensure_ollama_running()

    service = LocalModelService()

    if args.health:
        print_health_dashboard(service)
        return

    user_prompt = " ".join(args.prompt).strip()

    if not user_prompt:
        # Launch conversational discovery & approval mode
        run_interactive_chat(service, session_id=args.session)
        return

    # Direct CLI goal passed
    console.print(Panel(f"[bold yellow]Proposed Goal:[/bold yellow] {user_prompt}", title="Autonomous Coding Agent"))

    if not args.yes:
        # Require explicit user approval before execution
        try:
            choice = console.input("[bold green]Approve and begin autonomous execution? [Y/n]: [/bold green]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Execution cancelled.[/yellow]")
            return

        if choice in ("n", "no", "cancel"):
            console.print("[yellow]Execution cancelled. Entering interactive chat mode...[/yellow]")
            run_interactive_chat(service, session_id=args.session)
            return

    console.print("[bold green]✓ Approved! Starting autonomous execution pipeline...[/bold green]")
    orchestrator = AgentOrchestrator(model_service=service)
    result = orchestrator.run(user_prompt, session_id=args.session)
    console.print("\n" + result.final_response)

if __name__ == "__main__":
    run_cli()
