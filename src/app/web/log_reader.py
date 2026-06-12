from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import AppConfig

config = AppConfig()


def _task_output_dir(task_key: str) -> Path:
    return config.outputs_path / task_key


def get_recent_logs(task_key: str, after_line: int = 0) -> list[dict]:
    log_file = _task_output_dir(task_key) / "info.log"
    if not log_file.exists():
        return []
    entries = []
    lines = log_file.read_text(encoding="utf-8").splitlines()
    for line in lines[after_line:]:
        line = line.strip()
        if not line:
            continue
        entry = {"raw": line}
        if "[STAGE_START]" in line:
            phase = line.split("[STAGE_START]")[1].split("started")[0].strip()
            entry["type"] = "stage_start"
            entry["phase"] = phase
        elif "[STAGE_END]" in line:
            entry["type"] = "stage_end"
            parts = line.split("[STAGE_END]")[1].strip()
            entry["raw_short"] = parts
        elif "[LLM]" in line:
            entry["type"] = "llm"
            entry["raw_short"] = line.split("[LLM]")[1].strip()
        elif "[ERROR]" in line:
            entry["type"] = "error"
            entry["raw_short"] = line.split("[ERROR]")[1].strip()
        elif "[ARTIFACT]" in line:
            entry["type"] = "artifact"
            entry["raw_short"] = line.split("[ARTIFACT]")[1].strip()
        else:
            entry["type"] = "info"
        entries.append(entry)
    return entries


def get_error_logs(task_key: str) -> str:
    log_file = _task_output_dir(task_key) / "error.log"
    if not log_file.exists():
        return ""
    return log_file.read_text(encoding="utf-8").strip()


def get_token_usage(task_key: str) -> dict:
    usage_file = _task_output_dir(task_key) / "token-usage.json"
    if not usage_file.exists():
        return {}
    return json.loads(usage_file.read_text(encoding="utf-8"))


def get_artifact_json(task_key: str, filename: str) -> dict:
    f = _task_output_dir(task_key) / filename
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding="utf-8"))
