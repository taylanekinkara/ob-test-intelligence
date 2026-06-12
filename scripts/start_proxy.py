#!/usr/bin/env python
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_CONFIG = _BASE / "config" / "litellm" / "config.yaml"
_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-ob-test-local")


def _is_running() -> bool:
    import httpx
    try:
        resp = httpx.get("http://localhost:4000/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def main():
    if _is_running():
        print("LiteLLM proxy already running on :4000")
        return

    print("Starting LiteLLM proxy on :4000...")
    env = {**os.environ, "LITELLM_MASTER_KEY": _MASTER_KEY}

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "litellm",
            "--config", str(_CONFIG),
            "--port", "4000",
            "--host", "0.0.0.0",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for i in range(30):
        time.sleep(1)
        if _is_running():
            print(f"LiteLLM proxy ready (pid={proc.pid})")
            return
        if proc.poll() is not None:
            print(f"LiteLLM proxy failed to start: {proc.stderr.read().decode()[:500]}")
            sys.exit(1)

    print("LiteLLM proxy did not become ready in 30s")
    sys.exit(1)


if __name__ == "__main__":
    main()
