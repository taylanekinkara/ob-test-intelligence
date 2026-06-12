from __future__ import annotations


import asyncio
import json
import re
from pathlib import Path

from app.config import AppConfig
from app.integrations.litellm_client import LiteLLMClient
from app.utils.context_loader import ContextLoader
from app.utils.files import read_json, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)

_REQUIRED_SCENARIO_TYPES = ["happy_path", "edge_case", "error_case"]


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


def _ensure_minimal_scenarios(scenarios: list[dict], test_item: dict) -> list[dict]:
    existing_types = {s.get("type") for s in scenarios}
    tid = test_item.get("id", "T0")
    target = test_item.get("target", "unknown")
    idx = len(scenarios)

    for stype in _REQUIRED_SCENARIO_TYPES:
        if stype not in existing_types:
            idx += 1
            if stype == "happy_path":
                scenarios.append({
                    "id": f"{tid}-S{idx}",
                    "test_item_id": tid,
                    "name": f"Happy path for {target}",
                    "type": "happy_path",
                    "steps": [{"action": "http_request", "method": "POST", "url": "/api/placeholder", "headers": {}, "body": {}}],
                    "assertions": [{"field": "status_code", "operator": "equals", "value": 200}],
                    "expected_status_code": 200,
                })
            elif stype == "edge_case":
                scenarios.append({
                    "id": f"{tid}-S{idx}",
                    "test_item_id": tid,
                    "name": f"Edge case for {target}",
                    "type": "edge_case",
                    "steps": [{"action": "http_request", "method": "POST", "url": "/api/placeholder", "headers": {}, "body": {}}],
                    "assertions": [{"field": "status_code", "operator": "equals", "value": 400}],
                    "expected_status_code": 400,
                })
            elif stype == "error_case":
                scenarios.append({
                    "id": f"{tid}-S{idx}",
                    "test_item_id": tid,
                    "name": f"Error case for {target}",
                    "type": "error_case",
                    "steps": [{"action": "http_request", "method": "POST", "url": "/api/placeholder", "headers": {}, "body": {}}],
                    "assertions": [{"field": "status_code", "operator": "equals", "value": 500}],
                    "expected_status_code": 500,
                })
    return scenarios


async def stage_scenario_generate(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    assessment = read_json(output_dir / "test-assessment.json") or {}
    code_analysis = read_json(output_dir / "code-analysis.json") or {}
    task_summary = read_json(output_dir / "task-summary.json") or {}

    domain = task_summary.get("domain", "")
    endpoints = code_analysis.get("endpoints_affected", [])

    context_loader = ContextLoader(config.context_path)
    domain_context = context_loader.load_for_phase("scenario_generate", domain)

    prompt_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "scenario_generator.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    all_scenarios = []
    test_items = assessment.get("test_items", [])

    for idx, item in enumerate(test_items):
        tid = item.get("id", "T0")
        target = item.get("target", "")
        test_type = item.get("test_type", "api")
        domain_item = item.get("domain", domain)

        item_scenarios = []
        try:
            prompt = prompt_template.format(
                task_key=task_key,
                test_item_id=tid,
                target=target,
                test_type=test_type,
                domain=domain_item,
                priority=item.get("priority", "p2"),
                endpoints=json.dumps(endpoints[:10], ensure_ascii=False),
                domain_context=domain_context,
                what_changed=task_summary.get("what_changed", ""),
                expected_behavior=task_summary.get("expected_behavior", ""),
                acceptance_criteria=json.dumps(task_summary.get("acceptance_criteria", []), ensure_ascii=False),
            )

            llm = LiteLLMClient(config, task_key=task_key, phase="scenario_generate")
            model = config.get_model_for_stage("scenario_generate")
            response = await llm.complete(model, messages=[{"role": "user", "content": prompt}])
            parsed = _parse_json_response(response)
            item_scenarios = parsed.get("scenarios", [])
        except Exception as e:
            log_error(task_key, "stage_scenario_generate", e, output_dir)
            logger.warning("scenario_generate_llm_fallback", item=tid, error=str(e))

        for s in item_scenarios:
            s.setdefault("test_item_id", tid)

        item_scenarios = _ensure_minimal_scenarios(item_scenarios, item)
        all_scenarios.extend(item_scenarios)

        if idx < len(test_items) - 1:
            await asyncio.sleep(2)

    result = {"scenarios": all_scenarios}
    write_json(output_dir / "test-scenarios.json", result)
    logger.info("scenario_generate_complete", task_key=task_key, count=len(all_scenarios))
    return {"test_scenarios": result}
