from __future__ import annotations


import asyncio
import subprocess

import httpx

from app.config import AppConfig
from app.utils.files import read_json, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


async def _health_check(url: str, max_attempts: int = 30, interval: int = 2) -> bool:
    for i in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(interval)
    return False


async def _start_docker(config: AppConfig, service: str) -> bool:
    compose_file = config.docker_compose_file
    cwd = config.ob_core_path / "src"
    if not cwd.exists():
        cwd = config.ob_core_path
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker-compose", "-f", compose_file, "up", "-d", service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return proc.returncode == 0
    except Exception as e:
        log_error(task_key, "stage_env_prepare", e, output_dir)
        logger.error("docker_start_failed", service=service, error=str(e))
        return False


async def stage_env_prepare(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    assessment = read_json(output_dir / "test-assessment.json") or {}
    env = assessment.get("environment", {})
    if isinstance(env, list):
        env = env[0] if env else {}
    test_type = env.get("type", "api") if isinstance(env, dict) else "api"

    api_url = f"http://localhost:{config.api_port}"
    web_url = f"http://localhost:{config.port}"
    api_healthy = await _health_check(f"{api_url}/health", max_attempts=2, interval=1)

    if not api_healthy and test_type in ("api", "web"):
        logger.info("starting_docker_api")
        docker_ok = await _start_docker(config, config.docker_api_service)
        if docker_ok:
            api_healthy = await _health_check(f"{api_url}/health", max_attempts=10, interval=3)

    web_healthy = False
    if test_type == "web":
        web_healthy = await _health_check(f"{web_url}/health", max_attempts=2, interval=1)
        if not web_healthy:
            logger.info("starting_docker_web")
            docker_ok = await _start_docker(config, config.docker_web_service)
            if docker_ok:
                web_healthy = await _health_check(f"{web_url}/health", max_attempts=10, interval=3)

    result = {
        "environment": test_type,
        "api_url": api_url,
        "api_healthy": api_healthy,
        "web_url": web_url,
        "web_healthy": web_healthy,
        "auth_configured": False,
        "test_credentials": {},
    }

    write_json(output_dir / "env-status.json", result)
    logger.info("env_prepare_complete", task_key=task_key, api_ok=api_healthy, web_ok=web_healthy)
    return {"env_prepare": result}
