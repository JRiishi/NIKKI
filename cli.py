import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure workspace in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.orchestrator.orchestrator import AgentOrchestrator
from src.service.model_service import LocalModelService

console = Console()

def run_cli():
    parser = argparse.ArgumentParser(description="Autonomous Software Engineering Agent (Local Multi-Model)")
    parser.add_argument("prompt", nargs="*", help="Goal or task description for the agent.")
    parser.add_argument("--session", "-s", type=str, default=None, help="Session ID to create or resume.")
    parser.add_argument("--health", action="store_true", help="Check local models and runtime health.")
    args = parser.parse_args()

    service = LocalModelService()

    if args.health:
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
        return

    user_prompt = " ".join(args.prompt).strip()
    if not user_prompt:
        console.print("[bold cyan]Enter engineering goal (type 'exit' to quit):[/bold cyan]")
        user_prompt = input(">>> ").strip()
        if user_prompt.lower() in ("exit", "quit", ""):
            return

    console.print(Panel(f"[bold yellow]Goal:[/bold yellow] {user_prompt}", title="Autonomous Coding Agent"))

    orchestrator = AgentOrchestrator(model_service=service)
    result = orchestrator.run(user_prompt, session_id=args.session)

    console.print("\n" + result.final_response)

if __name__ == "__main__":
    run_cli()

