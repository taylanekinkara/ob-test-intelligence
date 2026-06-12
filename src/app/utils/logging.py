from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog


_TASK_LOGGERS: dict[str, dict[str, logging.Logger]] = {}


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper()))


def setup_task_logging(task_key: str, output_dir: Path) -> None:
    if task_key in _TASK_LOGGERS:
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    info_handler = logging.FileHandler(
        output_dir / "info.log", encoding="utf-8", mode="w"
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    error_handler = logging.FileHandler(
        output_dir / "error.log", encoding="utf-8", mode="w"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s\n"))

    root = logging.getLogger()
    root.addHandler(info_handler)
    root.addHandler(error_handler)

    _TASK_LOGGERS[task_key] = {
        "info": info_handler,
        "error": error_handler,
    }


def log_stage_start(task_key: str, phase: str, output_dir: Path) -> None:
    _append_log(output_dir / "info.log", f"[STAGE_START] {phase} started for {task_key}")


def log_stage_end(task_key: str, phase: str, output_dir: Path, duration_ms: int, success: bool = True) -> None:
    status = "OK" if success else "FAILED"
    _append_log(output_dir / "info.log", f"[STAGE_END] {phase} {status} for {task_key} ({duration_ms}ms)")


def log_error(task_key: str, phase: str, error: Exception | str, output_dir: Path) -> None:
    if isinstance(error, Exception):
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        error_text = "".join(tb)
    else:
        error_text = str(error)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    entry = f"{timestamp} [ERROR] {phase}: {error_text}\n"
    _append_raw(output_dir / "error.log", entry)
    _append_raw(output_dir / "info.log", entry)


def log_llm_call(task_key: str, phase: str, model: str, prompt_len: int, response_len: int, duration_ms: int, output_dir: Path, error: str = "", prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0) -> None:
    status = "OK" if not error else f"FAILED: {error}"
    token_info = f" tokens={total_tokens}({prompt_tokens}+{completion_tokens})" if total_tokens else ""
    entry = f"[LLM] {phase} model={model} prompt={prompt_len}chars response={response_len}chars duration={duration_ms}ms{token_info} {status}"
    _append_log(output_dir / "info.log", entry)


def log_artifact(task_key: str, name: str, path: Path, size: int) -> None:
    _append_log(path.parent / "info.log", f"[ARTIFACT] {name} -> {path.name} ({size} bytes)")


def _append_log(path: Path, message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"{timestamp} {message}\n"
    _append_raw(path, line)


def _append_raw(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
