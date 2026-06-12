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


async def stage_verify(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    test_results = read_json(output_dir / "test-results.json") or {}
    task_summary = read_json(output_dir / "task-summary.json") or {}
    scenarios_data = read_json(output_dir / "test-scenarios.json") or {}
    domain = task_summary.get("domain", "")

    total = test_results.get("total_scenarios", 0)
    passed = test_results.get("passed", 0)
    coverage = (passed / total * 100) if total > 0 else 0

    findings = []
    false_negatives = []

    for r in test_results.get("results", []):
        if not r["passed"]:
            error = r.get("error", "")
            is_env_error = any(kw in error.lower() for kw in ["connection", "timeout", "refused"])
            is_test_error = any(kw in error.lower() for kw in ["json", "parse", "key"])

            if is_env_error:
                false_negatives.append({
                    "scenario": r["scenario_id"],
                    "reason": "environment_error",
                    "detail": f"Connection/timeout error: {error[:200]}",
                })
                findings.append({
                    "severity": "high",
                    "type": "environment_issue",
                    "description": f"Scenario {r['scenario_id']} failed due to environment error",
                    "affected_scenario": r["scenario_id"],
                    "recommendation": "Check if API is running and accessible",
                })
            elif is_test_error:
                false_negatives.append({
                    "scenario": r["scenario_id"],
                    "reason": "test_scenario_error",
                    "detail": f"Parse/key error: {error[:200]}",
                })
                findings.append({
                    "severity": "medium",
                    "type": "test_error",
                    "description": f"Scenario {r['scenario_id']} has test infrastructure issues",
                    "affected_scenario": r["scenario_id"],
                    "recommendation": "Fix test scenario or assertion format",
                })
            else:
                for ar in r.get("assertions", []):
                    if not ar.get("passed", True):
                        findings.append({
                            "severity": "medium",
                            "type": "potential_bug",
                            "description": f"Assertion failed on {ar.get('field', '')}: expected {ar.get('expected', '')}, got {ar.get('actual', '')}",
                            "affected_scenario": r["scenario_id"],
                            "recommendation": f"Investigate why {ar.get('field', '')} did not match expected value",
                        })

    context_loader = ContextLoader(str(config.context_path))
    context = context_loader.load_for_phase("verify", domain)

    try:
        prompt_template = (Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "result_verifier.md").read_text(encoding="utf-8")
        prompt = prompt_template.format(
            test_results=json.dumps(test_results, ensure_ascii=False)[:8000],
            task_summary=json.dumps(task_summary, ensure_ascii=False)[:2000],
            context=context[:3000],
            scenarios=json.dumps(scenarios_data, ensure_ascii=False)[:4000],
        )
        llm = LiteLLMClient(config, task_key=task_key, phase="verify")
        model = config.get_model_for_stage("verify")
        response = await llm.complete(model, messages=[{"role": "user", "content": prompt}])
        llm_analysis = _parse_json_response(response)
        if llm_analysis.get("findings"):
            findings.extend(llm_analysis["findings"])
        if llm_analysis.get("false_negatives"):
            false_negatives.extend(llm_analysis["false_negatives"])
    except Exception as e:
        log_error(task_key, "stage_verify", e, output_dir)
        logger.warning("verify_llm_failed", error=str(e))

    verdict = "PASS" if coverage >= 100 and not any(f["severity"] == "high" for f in findings) else \
              "PASS_WITH_NOTES" if coverage >= 70 else "FAIL"

    result = {
        "overall_verdict": verdict,
        "coverage_percentage": round(coverage, 1),
        "test_quality": "good" if coverage >= 70 else "needs_improvement",
        "findings": findings,
        "false_positives": [],
        "false_negatives": false_negatives,
    }

    write_json(output_dir / "verification-report.json", result)
    logger.info("verify_complete", task_key=task_key, verdict=verdict, coverage=round(coverage, 1))
    return {"verification_report": result}
