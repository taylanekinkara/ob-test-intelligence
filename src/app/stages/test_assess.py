from __future__ import annotations


import json
import re
from pathlib import Path

from app.config import AppConfig
from app.integrations.litellm_client import LiteLLMClient
from app.utils.context_loader import ContextLoader
from app.utils.files import read_json, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)

_ALWAYS_TEST_DOMAINS = {"payment"}
_ALWAYS_TEST_LAYERS = {"api_controller", "service"}


def _parse_json_response(text: str) -> dict:
    cb_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if cb_match:
        try:
            return json.loads(cb_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}
        return {}


def _enforce_hard_rules(test_items: list[dict], skip_items: list[dict]) -> tuple[list[dict], list[dict]]:
    promoted = []
    remaining_skip = []
    for item in skip_items:
        domain = item.get("domain", "")
        layer = item.get("layer", "")
        if domain in _ALWAYS_TEST_DOMAINS or layer in _ALWAYS_TEST_LAYERS:
            item["priority"] = "p0" if domain == "payment" else "p1"
            item["test_type"] = "api"
            item["reason"] = f"Hard rule: {domain or layer} always requires testing"
            test_items.append(item)
            promoted.append(item["target"])
        else:
            remaining_skip.append(item)
    return test_items, remaining_skip


async def stage_test_assess(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    code_analysis = read_json(output_dir / "code-analysis.json") or {}
    impact_analysis = read_json(output_dir / "impact-analysis.json") or {}
    task_summary = read_json(output_dir / "task-summary.json") or {}

    domain = task_summary.get("domain", "")
    risk_level = impact_analysis.get("overall_risk", "low")
    risk_thresholds = config.get_risk_thresholds()

    context_loader = ContextLoader(config.context_path)
    domain_context = context_loader.load_for_phase("test_assess", domain)

    files_changed = code_analysis.get("files_changed", [])
    files_desc = json.dumps(files_changed, indent=2, ensure_ascii=False)
    risk_factors = json.dumps(impact_analysis.get("risk_factors", []), ensure_ascii=False)
    regression_areas = json.dumps(impact_analysis.get("regression_areas", []), ensure_ascii=False)

    llm_test_items = []
    llm_skip_items = []
    llm_environment = {}
    try:
        prompt_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "test_assessor.md"
        prompt_template = prompt_path.read_text(encoding="utf-8")

        prompt = prompt_template.format(
            task_key=task_key,
            title=task_summary.get("title", ""),
            domain=domain,
            risk_level=risk_level,
            what_changed=task_summary.get("what_changed", ""),
            expected_behavior=task_summary.get("expected_behavior", ""),
            acceptance_criteria=json.dumps(task_summary.get("acceptance_criteria", []), ensure_ascii=False),
            files_changed=files_desc,
            layers_affected=json.dumps(code_analysis.get("layers_affected", []), ensure_ascii=False),
            domains_affected=json.dumps(code_analysis.get("domains_affected", []), ensure_ascii=False),
            risk_factors=risk_factors,
            regression_areas=regression_areas,
            domain_context=domain_context,
        )

        llm = LiteLLMClient(config, task_key=task_key, phase="test_assess")
        model = config.get_model_for_stage("test_assess")
        response = await llm.complete(model, messages=[{"role": "user", "content": prompt}])

        parsed = _parse_json_response(response)
        llm_test_items = parsed.get("test_items", [])
        llm_skip_items = parsed.get("skip_items", [])
        llm_environment = parsed.get("environment", {})
    except Exception as e:
        log_error(task_key, "stage_test_assess", e, output_dir)
        logger.warning("test_assess_llm_fallback", error=str(e))

    if llm_test_items:
        for i, item in enumerate(llm_test_items):
            item.setdefault("id", f"T{i + 1}")
            item.setdefault("test_type", "api")
            item.setdefault("priority", "p2")
            item.setdefault("risk", risk_level)
        test_items = llm_test_items
    else:
        test_items = _fallback_test_items(files_changed, risk_level)

    if llm_skip_items:
        skip_items = llm_skip_items
    else:
        skip_items = _fallback_skip_items(files_changed, test_items)

    test_items, skip_items = _enforce_hard_rules(test_items, skip_items)

    environment = llm_environment if llm_environment else {
        "type": "api" if any(t.get("test_type") == "api" for t in test_items) else "web",
        "requires_docker": True,
        "docker_compose": config.docker_compose_file,
        "api_url": f"http://localhost:{config.api_port}",
    }

    result = {
        "needs_testing": len(test_items) > 0,
        "test_items": test_items,
        "skip_items": skip_items,
        "environment": environment,
    }

    write_json(output_dir / "test-assessment.json", result)
    logger.info("test_assess_complete", task_key=task_key, items=len(test_items))
    return {"test_assessment": result}


def _fallback_test_items(files_changed: list[dict], risk_level: str) -> list[dict]:
    items = []
    for i, f in enumerate(files_changed):
        layer = f.get("layer", "")
        change_type = f.get("change_type", "")
        domain = f.get("domain", "")
        if domain in _ALWAYS_TEST_DOMAINS or change_type in ("api_change", "service_logic", "new_api"):
            items.append({
                "id": f"T{i + 1}",
                "target": f["path"],
                "test_type": "api" if layer in ("api_controller", "service") else "api",
                "priority": "p0" if domain == "payment" else "p2",
                "reason": f"{change_type} in {layer}",
                "layer": layer,
                "domain": domain,
                "risk": risk_level,
            })
    return items


def _fallback_skip_items(files_changed: list[dict], test_items: list[dict]) -> list[dict]:
    tested_targets = {t.get("target") for t in test_items}
    skips = []
    for f in files_changed:
        if f["path"] not in tested_targets:
            skips.append({
                "target": f["path"],
                "reason": f"{f.get('change_type', '')} in {f.get('layer', '')} does not require automated test",
                "suggested_action": "manual_check",
                "domain": f.get("domain", ""),
                "layer": f.get("layer", ""),
            })
    return skips
