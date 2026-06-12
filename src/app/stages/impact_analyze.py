from __future__ import annotations


import json
import re
from pathlib import Path

from app.config import AppConfig
from app.integrations.graphify_client import GraphifyClient
from app.integrations.litellm_client import LiteLLMClient
from app.utils.context_loader import ContextLoader
from app.utils.files import read_json, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


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


async def stage_impact_analyze(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    code_analysis = read_json(output_dir / "code-analysis.json")
    if not code_analysis:
        logger.warning("impact_analyze_no_code_analysis")
        return {"impact_analysis": {}}

    task_summary = read_json(output_dir / "task-summary.json") or {}
    domain = task_summary.get("domain", code_analysis.get("domains_affected", [""])[0] if code_analysis.get("domains_affected") else "")

    seed_files = [f["path"] for f in code_analysis.get("files_changed", [])]

    graphify = GraphifyClient(config)
    try:
        impact = await graphify.impact_query(seed_files[:50])
    except Exception as e:
        log_error(task_key, "stage_impact_analyze", e, output_dir)
        logger.warning("graphify_query_failed", error=str(e))
        impact = {"one_hop": {"count": 0, "files": []}, "two_hop": {"count": 0, "highlights": []}, "error": str(e)[:200]}

    context_loader = ContextLoader(config.context_path)
    domain_context = context_loader.load_for_phase("impact_assess", domain)

    one_hop_files = impact.get("one_hop", {}).get("files", [])
    two_hop = impact.get("two_hop", {})
    communities = impact.get("communities", [])
    god_nodes = impact.get("god_nodes", [])

    parsed = {}
    try:
        prompt_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "impact_assessor.md"
        prompt_template = prompt_path.read_text(encoding="utf-8")

        prompt = prompt_template.format(
            seed_files=json.dumps(seed_files, ensure_ascii=False),
            one_hop_files=json.dumps(one_hop_files[:50], ensure_ascii=False),
            two_hop=json.dumps(two_hop, ensure_ascii=False),
            communities=json.dumps(communities[:20], ensure_ascii=False),
            god_nodes=json.dumps(god_nodes[:20], ensure_ascii=False),
            domains_affected=json.dumps(code_analysis.get("domains_affected", []), ensure_ascii=False),
            layers_affected=json.dumps(code_analysis.get("layers_affected", []), ensure_ascii=False),
            domain_context=domain_context,
        )

        llm = LiteLLMClient(config, task_key=task_key, phase="impact_analyze")
        model = config.get_model_for_stage("impact_assess")
        response = await llm.complete(model, messages=[{"role": "user", "content": prompt}])
        parsed = _parse_json_response(response)
    except Exception as e:
        log_error(task_key, "stage_impact_analyze", e, output_dir)
        logger.warning("impact_analyze_llm_fallback", error=str(e))

    llm_risk = parsed.get("overall_risk", "")
    static_risk = _assess_risk(code_analysis)
    final_risk = llm_risk if llm_risk in ("high", "medium", "low") else static_risk

    result = {
        "seed_files": seed_files,
        "one_hop": impact.get("one_hop", {"count": 0, "files": []}),
        "two_hop": two_hop or {"count": 0, "highlights": []},
        "communities_affected": communities,
        "god_nodes_affected": god_nodes,
        "overall_risk": final_risk,
        "regression_areas": parsed.get("regression_areas", []),
        "risk_factors": parsed.get("risk_factors", []),
        "llm_analysis": parsed.get("analysis", ""),
    }

    write_json(output_dir / "impact-analysis.json", result)
    logger.info("impact_analyze_complete", task_key=task_key, risk=result["overall_risk"])
    return {"impact_analysis": result}


def _assess_risk(code_analysis: dict) -> str:
    domains = code_analysis.get("domains_affected", [])
    layers = code_analysis.get("layers_affected", [])
    if "payment" in domains:
        return "high"
    if any(l in layers for l in ["api_controller", "service"]):
        return "medium"
    return "low"
