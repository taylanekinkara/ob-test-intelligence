from __future__ import annotations


import time
from datetime import datetime, timezone

import httpx

from app.config import AppConfig
from app.utils.assertion_engine import check_assertion
from app.utils.files import read_json, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


async def _execute_scenario(client: httpx.AsyncClient, scenario: dict, base_url: str) -> dict:
    start = time.time()
    step = scenario.get("steps", [{}])[0] if scenario.get("steps") else {}
    method = step.get("method", "GET").upper()
    url = f"{base_url}{step.get('url', '/')}"
    headers = step.get("headers", {})
    body = step.get("body")

    try:
        if method in ("POST", "PUT", "PATCH"):
            resp = await client.request(method=method, url=url, headers=headers, json=body)
        else:
            resp = await client.request(method=method, url=url, headers=headers)

        assertion_results = []
        for assertion in scenario.get("assertions", []):
            assertion_results.append(check_assertion(resp, assertion))

        passed = all(ar["passed"] for ar in assertion_results)
        duration = int((time.time() - start) * 1000)

        return {
            "scenario_id": scenario["id"],
            "name": scenario.get("name", ""),
            "passed": passed,
            "status_code": resp.status_code,
            "assertions": assertion_results,
            "duration_ms": duration,
            "error": "",
        }
    except Exception as e:
        duration = int((time.time() - start) * 1000)
        return {
            "scenario_id": scenario["id"],
            "name": scenario.get("name", ""),
            "passed": False,
            "status_code": 0,
            "assertions": [],
            "duration_ms": duration,
            "error": str(e),
        }


async def stage_test_execute(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    try:
        scenarios_data = read_json(output_dir / "test-scenarios.json") or {}
        scenarios = scenarios_data.get("scenarios", [])
        env_status = read_json(output_dir / "env-status.json") or {}
        base_url = env_status.get("api_url", f"http://localhost:{config.api_port}")
        api_healthy = env_status.get("api_healthy", False)

        if not api_healthy:
            logger.warning("test_execute_skipped_no_api", task_key=task_key, scenarios=len(scenarios))
            results = []
            for s in scenarios:
                results.append({
                    "scenario_id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "passed": False,
                    "status_code": 0,
                    "assertions": [],
                    "duration_ms": 0,
                    "error": "skipped: API not available",
                })

            result = {
                "execution_time": datetime.now(timezone.utc).isoformat(),
                "total_scenarios": len(results),
                "passed": 0,
                "failed": 0,
                "skipped": len(results),
                "results": results,
                "note": "API ortami hazir degil. Senaryolar kaydedildi ama calistirilmadi. API ayaga kaldirildiktan sonra pipeline'i yeniden calistirin.",
            }

            write_json(output_dir / "test-results.json", result)
            logger.info("test_execute_skipped", task_key=task_key, skipped=len(results))
            return {"test_results": result}

        results = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for scenario in scenarios:
                r = await _execute_scenario(client, scenario, base_url)
                results.append(r)
                status = "PASS" if r["passed"] else "FAIL"
                logger.info("scenario_result", scenario=r["scenario_id"], status=status, ms=r["duration_ms"])

        passed_count = sum(1 for r in results if r["passed"])
        failed_count = len(results) - passed_count

        result = {
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "total_scenarios": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "skipped": 0,
            "results": results,
        }

        write_json(output_dir / "test-results.json", result)
        logger.info("test_execute_complete", task_key=task_key, passed=passed_count, failed=failed_count, total=len(results))
        return {"test_results": result}
    except Exception as e:
        log_error(task_key, "stage_test_execute", e, output_dir)
        logger.error("test_execute_failed", task_key=task_key, error=str(e))
        raise
