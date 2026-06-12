from __future__ import annotations


import json
from pathlib import Path

from app.config import AppConfig
from app.integrations.litellm_client import LiteLLMClient
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


def _check_jira_raw(output_dir: Path) -> dict:
    jira_file = output_dir / "jira-raw.json"
    if jira_file.exists():
        data = json.loads(jira_file.read_text(encoding="utf-8"))
        return {
            "jira_raw_exists": True,
            "has_issue": bool(data.get("issue")),
            "has_comments": "comments" in data,
            "has_dev_info": "dev_info" in data,
        }
    return {"jira_raw_exists": False}


async def stage_ensure_ready(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key
    output_dir.mkdir(parents=True, exist_ok=True)

    checks = {}
    warnings = []

    venv_path = Path(__file__).resolve().parent.parent.parent.parent / ".venv"
    checks["venv"] = venv_path.exists()

    llm = LiteLLMClient(config)
    checks["llm_available"] = await llm.health()
    if not checks["llm_available"]:
        warnings.append("GitHub Copilot erisimi saglanamadi, LLM fallback aktif")

    checks["copilot_auth"] = (Path.home() / ".config" / "litellm" / "github_copilot").exists()

    checks["graphify_graph"] = (config.graphify_path / "graph.json").exists()
    checks["graphify_path"] = str(config.graphify_path)
    if not checks["graphify_graph"]:
        warnings.append(f"Graphify graph.json bulunamadi: {config.graphify_path}")

    checks["context_exists"] = config.context_path.exists()
    checks["context_path"] = str(config.context_path)
    if not checks["context_exists"]:
        warnings.append(f"obiletcontext bulunamadi: {config.context_path}")

    checks["ob_core_exists"] = config.ob_core_path.exists()
    checks["ob_core_path"] = str(config.ob_core_path)
    if not checks["ob_core_exists"]:
        warnings.append(f"ob-core repo bulunamadi: {config.ob_core_path}")

    jira_check = _check_jira_raw(output_dir)
    checks["jira_raw"] = jira_check["jira_raw_exists"]
    if not jira_check["jira_raw_exists"]:
        warnings.append(f"Jira verisi bulunamadi: outputs/tests/{task_key}/jira-raw.json")

    result = {
        "checks": checks,
        "warnings": warnings,
    }

    if warnings:
        for w in warnings:
            logger.warning("ensure_ready_warning", message=w)
        logger.warning("ensure_ready_incomplete", warnings=len(warnings))
    else:
        logger.info("ensure_ready_ok")

    return {"ensure_ready": result}
