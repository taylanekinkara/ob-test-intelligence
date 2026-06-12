from __future__ import annotations

import asyncio
import json
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class PlaywrightRunner:
    def __init__(self) -> None:
        pass

    async def execute_test(self, script_path: str, timeout: int = 60) -> dict[str, Any]:
        cmd = ["python", "-m", "playwright", "test", script_path, "--reporter=json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"status": "timeout", "passed": False, "error": f"Test timed out after {timeout}s"}

        if proc.returncode != 0:
            return {
                "status": "failed",
                "passed": False,
                "error": stderr.decode()[:500],
                "output": stdout.decode()[:500],
            }

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            return {"status": "passed", "passed": True, "output": stdout.decode()[:500]}
