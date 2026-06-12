#!/usr/bin/env python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_SRC = _BASE / "src"
_VENV = _BASE / ".venv"
_PYTHON = _VENV / "Scripts" / "python.exe" if sys.platform == "win32" else _VENV / "bin" / "python"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    args = sys.argv[2:]

    if cmd == "launch":
        _ensure_venv()
        _run_cli("launch", *args)
    elif cmd == "poll":
        _run_cli("poll", *args)
    elif cmd == "resume":
        _ensure_venv()
        _run_cli("resume", *args)
    elif cmd == "status":
        _run_cli("status", *args)
    elif cmd == "smoke":
        _run_cli("smoke", *args)
    elif cmd == "web":
        _start_web()
    elif cmd == "fetch-jira":
        _fetch_jira(*args)
    elif cmd == "setup":
        _setup()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


def _ensure_venv():
    if not _VENV.exists():
        print("Creating .venv...")
        subprocess.run([sys.executable, "-m", "venv", str(_VENV)], check=True)
        pip = str(_VENV / "Scripts" / "pip.exe") if sys.platform == "win32" else str(_VENV / "bin" / "pip")
        subprocess.run([pip, "install", "-r", str(_BASE / "requirements.txt")], check=True)


def _run_cli(cmd: str, *args: str):
    python = str(_PYTHON) if _PYTHON.exists() else sys.executable
    subprocess.run(
        [python, "-m", "app.cli", cmd, *args],
        cwd=str(_SRC),
        env={**__import__("os").environ, "PYTHONPATH": str(_SRC)},
    )


def _start_web():
    python = str(_PYTHON) if _PYTHON.exists() else sys.executable
    subprocess.run(
        [python, "-m", "uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", "8081"],
        cwd=str(_SRC),
        env={**__import__("os").environ, "PYTHONPATH": str(_SRC)},
    )


def _fetch_jira(*args: str):
    python = str(_PYTHON) if _PYTHON.exists() else sys.executable
    subprocess.run(
        [python, str(_BASE / "scripts" / "fetch_jira.py"), *args],
        cwd=str(_BASE),
    )


def _setup():
    subprocess.run(
        [sys.executable, str(_BASE / "scripts" / "setup.py")],
        cwd=str(_BASE),
    )


if __name__ == "__main__":
    main()
