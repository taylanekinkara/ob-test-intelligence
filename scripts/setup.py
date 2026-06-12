#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_DOTENV = _BASE / ".env"
_DOTENV_EXAMPLE = _BASE / ".env.example"
_REQUIREMENTS = _BASE / "requirements.txt"
_VENV = _BASE / ".venv"

_PROMPTstyle = {"hl": "\033[1;36m", "dim": "\033[2m", "ok": "\033[1;32m", "warn": "\033[1;33m", "err": "\033[1;31m", "rst": "\033[0m"}


def _p(tag: str, msg: str):
    colors = {"OK": _PROMPTstyle["ok"], "WARN": _PROMPTstyle["warn"], "ERR": _PROMPTstyle["err"], "INFO": _PROMPTstyle["hl"]}
    c = colors.get(tag, "")
    print(f"{c}[{tag}]{_PROMPTstyle['rst']} {msg}")


def _ask(prompt: str, default: str = "") -> str:
    hint = f" {_PROMPTstyle['dim']}[{default}]{_PROMPTstyle['rst']}" if default else ""
    val = input(f"  {prompt}{hint}: ").strip()
    return val or default


def _ask_path(prompt: str, default: str = "") -> str:
    while True:
        raw = _ask(prompt, default)
        if not raw:
            return ""
        p = Path(raw)
        if p.exists():
            return str(p)
        _p("WARN", f"Path not found: {raw} — press Enter to skip or provide correct path")
        retry = input(f"  New path (Enter to skip): ").strip()
        if not retry:
            return ""
        if Path(retry).exists():
            return str(Path(retry))


def _auto_detect(candidates: list[str]) -> str:
    for root in [Path.home() / "repos", Path.home() / "projects", Path("/repos")]:
        if not root.exists():
            continue
        for name in candidates:
            p = root / name
            if p.exists():
                return str(p)
    return ""


def _venv_python() -> str:
    if sys.platform == "win32":
        return str(_VENV / "Scripts" / "python.exe")
    return str(_VENV / "bin" / "python")


def _venv_pip() -> str:
    if sys.platform == "win32":
        return str(_VENV / "Scripts" / "pip.exe")
    return str(_VENV / "bin" / "pip")


def _create_venv():
    if _VENV.exists():
        _p("OK", f".venv already exists at {_VENV}")
        return
    _p("INFO", "Creating .venv ...")
    subprocess.run([sys.executable, "-m", "venv", str(_VENV)], check=True)
    _p("OK", ".venv created")


def _install_requirements():
    if not _REQUIREMENTS.exists():
        _p("ERR", f"requirements.txt not found at {_REQUIREMENTS}")
        sys.exit(1)
    _p("INFO", "Installing requirements ...")
    subprocess.run([_venv_pip(), "install", "-r", str(_REQUIREMENTS)], check=True)
    _p("OK", "Requirements installed")


def _configure_env():
    if _DOTENV.exists():
        _p("OK", f".env already exists at {_DOTENV}")
        return

    _p("INFO", "Configuring .env ...")
    print()

    env_lines = []

    ob_core_default = _auto_detect(["obilet-core-v2", "ob-core", "obilet-core"])
    ob_core = _ask_path("OB_CORE_PATH (obilet-core-v2 repo path)", ob_core_default)

    graphify_default = _auto_detect(["graphify-out", "graphify"])
    graphify = _ask_path("GRAPHIFY_PATH (graphify repo path)", graphify_default)

    context_default = _auto_detect(["obiletcontext"])
    context = _ask_path("CONTEXT_PATH (obiletcontext path)", context_default)

    api_key = _ask("OPENAI_API_KEY (z.ai API key)")
    base_url = _ask("OPENAI_BASE_URL", "https://api.z.ai/api/paas/v4/")

    env_lines.append(f"LITELLM_MASTER_KEY=sk-ob-test-local")
    env_lines.append(f"OB_CORE_PATH={ob_core}")
    env_lines.append(f"GRAPHIFY_PATH={graphify}")
    env_lines.append(f"CONTEXT_PATH={context}")
    env_lines.append(f"API_PORT=8080")
    env_lines.append(f"WEB_PORT=8081")
    env_lines.append(f"LLM_PROFILE=standard")
    env_lines.append(f"")
    env_lines.append(f"OPENAI_API_KEY={api_key}")
    env_lines.append(f"OPENAI_BASE_URL={base_url}")

    _DOTENV.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    _p("OK", f".env written to {_DOTENV}")

    jira_email = _ask("OB_JIRA_EMAIL (Jira email, optional)")
    jira_token = _ask("OB_JIRA_API_TOKEN (Jira API token, optional)")
    jira_base = _ask("OB_JIRA_BASE_URL", "https://obilet.atlassian.net")

    if jira_email and jira_token:
        extra = [
            "",
            f"OB_JIRA_BASE_URL={jira_base}",
            f"OB_JIRA_EMAIL={jira_email}",
            f"OB_JIRA_API_TOKEN={jira_token}",
        ]
        with open(_DOTENV, "a", encoding="utf-8") as f:
            f.write("\n".join(extra) + "\n")
        _p("OK", "Jira credentials added to .env")


def _verify():
    _p("INFO", "Verifying setup ...")
    print()

    checks = [
        (".venv", _VENV.exists()),
        (".env", _DOTENV.exists()),
        ("requirements.txt", _REQUIREMENTS.exists()),
    ]

    all_ok = True
    for name, ok in checks:
        tag = "OK" if ok else "ERR"
        _p(tag, name)
        if not ok:
            all_ok = False

    if _DOTENV.exists():
        lines = _DOTENV.read_text(encoding="utf-8").splitlines()
        for key in ["OB_CORE_PATH", "OPENAI_API_KEY"]:
            found = any(line.startswith(f"{key}=") and len(line.split("=", 1)[1].strip()) > 0 for line in lines)
            tag = "OK" if found else "WARN"
            _p(tag, f".env/{key} {'set' if found else 'not set'}")
            if not found:
                all_ok = False

    print()
    if all_ok:
        _p("OK", "Setup complete! Ready to run pipeline.")
    else:
        _p("WARN", "Setup incomplete. Some items need attention.")

    print()
    print(f"  {_PROMPTstyle['hl']}Next steps:{_PROMPTstyle['rst']}")
    print(f"  1. Run: python scripts/ob_test_run.py launch <TASK_KEY>")
    print(f"  2. Or ask your AI agent: 'PDB-12345 test et'")


def main():
    print(f"\n  {_PROMPTstyle['hl']}ob-test-intelligence Setup{_PROMPTstyle['rst']}\n")

    _create_venv()
    _install_requirements()
    _configure_env()
    _verify()


if __name__ == "__main__":
    main()
