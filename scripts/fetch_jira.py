#!/usr/bin/env python
"""Fetch Jira issue data and save as jira-raw.json.

Tries in order:
1. Jira REST API (with .env credentials)
2. Jira CLI (npm jira-cli, if installed)
3. Stub (empty placeholder)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_BASE = Path(__file__).resolve().parent.parent
_ENV_FILE = _BASE / ".env"
_OUTPUTS = _BASE / "outputs" / "tests"


def _load_env() -> dict[str, str]:
    env = {}
    if not _ENV_FILE.exists():
        return env
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def _fetch_rest(task_key: str, env: dict[str, str]) -> dict | None:
    base_url = env.get("OB_JIRA_BASE_URL", "")
    email = env.get("OB_JIRA_EMAIL", "")
    token = env.get("OB_JIRA_API_TOKEN", "")
    if not all([base_url, email, token]):
        return None

    import base64
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    api = f"{base_url}/rest/api/3"

    try:
        req = Request(f"{api}/issue/{task_key}", headers=headers)
        issue = json.loads(urlopen(req, timeout=30).read().decode())

        dev_info = {"branches": [], "pullRequests": [], "repositories": []}
        try:
            dev_req = Request(f"{api}/issue/{task_key}/devinfo", headers=headers)
            dev_resp = urlopen(dev_req, timeout=15).read().decode()
            dev_data = json.loads(dev_resp)
            if isinstance(dev_data, dict):
                dev_info = {
                    "branches": dev_data.get("branches", []),
                    "pullRequests": dev_data.get("pullRequests", []),
                    "repositories": dev_data.get("repositories", []),
                }
        except Exception:
            pass

        comments: list[dict] = []
        try:
            cmt_req = Request(f"{api}/issue/{task_key}/comment", headers=headers)
            cmt_resp = urlopen(cmt_req, timeout=15).read().decode()
            cmt_data = json.loads(cmt_resp)
            comments = cmt_data.get("comments", [])
        except Exception:
            pass

        return {"issue": issue, "comments": comments, "dev_info": dev_info}
    except HTTPError as e:
        print(f"Jira REST API error: {e.code} {e.reason}")
        return None
    except URLError as e:
        print(f"Jira REST API unreachable: {e.reason}")
        return None
    except Exception as e:
        print(f"Jira REST API failed: {e}")
        return None


def _fetch_cli(task_key: str) -> dict | None:
    try:
        result = subprocess.run(
            ["jira", "issue", "view", task_key, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        issue = json.loads(result.stdout)
        return {"issue": issue, "comments": [], "dev_info": {"branches": [], "pullRequests": [], "repositories": []}}
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _create_stub(task_key: str) -> dict:
    return {
        "issue": {"key": task_key, "fields": {"summary": task_key, "description": ""}},
        "comments": [],
        "dev_info": {"branches": [], "pullRequests": [], "repositories": []},
    }


def fetch(task_key: str) -> Path:
    output_dir = _OUTPUTS / task_key
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "jira-raw.json"

    env = {**os.environ, **_load_env()}

    data = _fetch_rest(task_key, env)
    source = "REST API"

    if data is None:
        print("REST API failed, trying Jira CLI...")
        data = _fetch_cli(task_key)
        source = "CLI"

    if data is None:
        print("CLI not available, creating stub...")
        data = _create_stub(task_key)
        source = "STUB"

    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{source}] jira-raw.json saved: {out_file}")
    return out_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_jira.py <TASK_KEY>")
        sys.exit(1)
    fetch(sys.argv[1])
