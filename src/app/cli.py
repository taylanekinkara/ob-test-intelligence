from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import AppConfig

app = typer.Typer(name="ob-test", help="oBilet Test Intelligence Pipeline")
console = Console()


def _check_web(port: int) -> bool:
    try:
        return urlopen(f"http://localhost:{port}/api/status", timeout=2).status == 200
    except Exception:
        return False


def _start_web_server(port: int) -> None:
    venv = Path(__file__).resolve().parent.parent.parent / ".venv" / "Scripts" / "python.exe"
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [str(venv), "-m", "uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def _ensure_web_open(config: AppConfig, task_key: str = "") -> None:
    port = config.port
    url = f"http://localhost:{port}/test/{task_key}" if task_key else f"http://localhost:{port}"
    already_running = _check_web(port)
    if not already_running:
        console.print("[dim]Starting web server...[/dim]")
        _start_web_server(port)
        started = False
        for _ in range(15):
            time.sleep(1)
            if _check_web(port):
                started = True
                break
        if not started:
            console.print("[yellow]Warning: web server did not start in time[/yellow]")
            return
    webbrowser.open(url)
    console.print(f"[dim]WEB_UI_OPENED {url}[/dim]")


def _run_async(coro):
    return asyncio.run(coro)


def _check_jira_raw(config: AppConfig, task_key: str) -> bool:
    jira_file = config.outputs_path / task_key / "jira-raw.json"
    return jira_file.exists()


def _ensure_jira_raw(config: AppConfig, task_key: str) -> None:
    output_dir = config.outputs_path / task_key
    output_dir.mkdir(parents=True, exist_ok=True)
    jira_file = output_dir / "jira-raw.json"

    if jira_file.exists():
        return

    stub = {
        "issue": {"key": task_key, "fields": {"summary": task_key, "description": ""}},
        "comments": [],
        "dev_info": {"branches": [], "pullRequests": []},
    }
    jira_file.write_text(json.dumps(stub, indent=2, ensure_ascii=False), encoding="utf-8")
    logger_msg = f"Stub jira-raw.json olusturuldu: {jira_file}"
    console.print(f"[dim]{logger_msg}[/dim]")


@app.command()
def launch(
    task_key: str = typer.Argument(..., help="Jira task key (e.g. PDB-12345)"),
    source: str = typer.Option("jira", "--source", "-s", help="Task source"),
    project_path: str = typer.Option("", "--project", "-p", help="Project path"),
) -> None:
    """Launch test pipeline for a task."""
    from app.orchestrator import PipelineOrchestrator

    config = AppConfig()
    console.print(Panel(f"[bold green]ob-test-intelligence[/bold green]\nTask: {task_key}", title="Launch"))

    _ensure_jira_raw(config, task_key)
    _ensure_web_open(config, task_key)

    async def _run():
        orch = PipelineOrchestrator(config)
        _register_default_stages(orch, config)
        state = await orch.run(task_key, source, project_path)
        _print_state(state)

    _run_async(_run())


@app.command()
def poll(
    task_key: str = typer.Argument(..., help="Task key to poll"),
) -> None:
    """Poll pipeline status."""
    config = AppConfig()
    from app.orchestrator import PipelineOrchestrator

    orch = PipelineOrchestrator(config)
    state = orch.get_state(task_key)
    if not state:
        console.print(f"[red]No test found for {task_key}[/red]")
        raise typer.Exit(1)
    _print_state(state)


@app.command()
def resume(
    task_key: str = typer.Argument(..., help="Task key to resume"),
    response: str = typer.Option("approve", "--response", "-r", help="User response"),
) -> None:
    """Resume pipeline after user checkpoint."""
    from app.orchestrator import PipelineOrchestrator

    config = AppConfig()
    _ensure_web_open(config)

    async def _run():
        orch = PipelineOrchestrator(config)
        _register_default_stages(orch, config)
        state = await orch.resume(task_key, response)
        _print_state(state)

    _run_async(_run())


@app.command()
def status() -> None:
    """Show all tests."""
    config = AppConfig()
    from app.orchestrator import PipelineOrchestrator

    orch = PipelineOrchestrator(config)
    tests = orch.list_tests()
    if not tests:
        console.print("[yellow]No tests found[/yellow]")
        return

    table = Table(title="ob-test-intelligence")
    table.add_column("Task Key", style="cyan")
    table.add_column("Phase", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Updated", style="dim")
    for t in tests:
        table.add_row(
            t.get("task_key", ""),
            t.get("current_phase", ""),
            t.get("task_source", ""),
            t.get("updated_at", "")[:19],
        )
    console.print(table)


@app.command()
def smoke() -> None:
    """Run smoke test - check system health."""
    config = AppConfig()
    checks = []

    checks.append(("Config loaded", bool(config.pipeline_phases)))
    checks.append(("ob-core path", config.ob_core_path.exists()))
    checks.append(("graphify path", (config.graphify_path / "graph.json").exists()))
    checks.append(("context path", config.context_path.exists()))
    checks.append(("outputs dir", config.outputs_path.parent.exists()))

    table = Table(title="Smoke Test")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    for name, ok in checks:
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]")
    console.print(table)


def _register_default_stages(orch, config):
    from app.stages.ensure_ready import stage_ensure_ready
    from app.stages.task_read import stage_task_read
    from app.stages.code_analyze import stage_code_analyze
    from app.stages.impact_analyze import stage_impact_analyze
    from app.stages.test_assess import stage_test_assess
    from app.stages.scenario_generate import stage_scenario_generate
    from app.stages.env_prepare import stage_env_prepare
    from app.stages.test_execute import stage_test_execute
    from app.stages.verify import stage_verify
    from app.stages.report import stage_report

    orch.register_stage("ensure_ready", stage_ensure_ready)
    orch.register_stage("task_read", stage_task_read)
    orch.register_stage("code_analyze", stage_code_analyze)
    orch.register_stage("impact_analyze", stage_impact_analyze)
    orch.register_stage("test_assess", stage_test_assess)
    orch.register_stage("scenario_generate", stage_scenario_generate)
    orch.register_stage("env_prepare", stage_env_prepare)
    orch.register_stage("test_execute", stage_test_execute)
    orch.register_stage("verify", stage_verify)
    orch.register_stage("report", stage_report)


def _print_state(state) -> None:
    console.print(Panel(
        f"[bold]Task:[/bold] {state.task_key}\n"
        f"[bold]Phase:[/bold] {state.current_phase}\n"
        f"[bold]Completed:[/bold] {', '.join(state.phases_completed) or 'none'}",
        title="Pipeline Status",
    ))


if __name__ == "__main__":
    app()
