from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _BASE_DIR / "config"

_OB_CORE_CANDIDATES = ["obilet-core-v2", "ob-core", "obilet-core", "core"]
_GRAPHIFY_CANDIDATES = ["graphify-out", "graphify"]
_CONTEXT_CANDIDATES = ["obiletcontext", "OBTaskManager"]
_SEARCH_ROOTS = [
    Path.home() / "repos",
    Path.home() / "projects",
    Path("/repos"),
]


def _load_yaml(filename: str) -> dict[str, Any]:
    path = _CONFIG_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _find_path(candidates: list[str], hint: str = "") -> Path | None:
    if hint:
        p = Path(hint)
        if p.exists():
            return p

    for root in _SEARCH_ROOTS:
        if not root.exists():
            continue
        for candidate in candidates:
            p = root / candidate
            if p.exists():
                return p
    return None


class AppConfig:
    _instance: AppConfig | None = None

    def __new__(cls) -> AppConfig:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._raw = _load_yaml("app.yaml")
        self._routing = _load_yaml("model_routing.yaml")
        self._thresholds = _load_yaml("thresholds.yaml")

    @property
    def app_name(self) -> str:
        return self._raw.get("app", {}).get("name", "ob-test-intelligence")

    @property
    def host(self) -> str:
        return self._raw.get("app", {}).get("host", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(os.getenv("WEB_PORT", self._raw.get("app", {}).get("port", 8081)))

    @property
    def ob_core_path(self) -> Path:
        hint = os.getenv("OB_CORE_PATH", self._raw.get("paths", {}).get("ob_core", ""))
        found = _find_path(_OB_CORE_CANDIDATES, hint)
        if found:
            return found
        return Path(hint) if hint else Path(".")

    @property
    def graphify_path(self) -> Path:
        hint = os.getenv("GRAPHIFY_PATH", self._raw.get("paths", {}).get("graphify", ""))
        found = _find_path(_GRAPHIFY_CANDIDATES, hint)
        if found:
            return found
        return Path(hint) if hint else Path(".")

    @property
    def context_path(self) -> Path:
        hint = os.getenv("CONTEXT_PATH", self._raw.get("paths", {}).get("context", ""))
        found = _find_path(_CONTEXT_CANDIDATES, hint)
        if found:
            return found
        return Path(hint) if hint else Path(".")

    @property
    def outputs_path(self) -> Path:
        return _BASE_DIR / self._raw.get("paths", {}).get("outputs", "outputs/tests")

    @property
    def api_port(self) -> int:
        return int(os.getenv("API_PORT", 8080))

    @property
    def llm_profile(self) -> str:
        return os.getenv("LLM_PROFILE", "copilot")

    @property
    def litellm_master_key(self) -> str:
        return os.getenv("LITELLM_MASTER_KEY", "sk-ob-test-local")

    @property
    def pipeline_phases(self) -> list[str]:
        profile = os.getenv("PIPELINE_PROFILE", "standard")
        profiles = self._raw.get("pipeline", {}).get("profiles", {})
        return profiles.get(profile, profiles.get("standard", {})).get("phases", [])

    @property
    def user_checkpoints(self) -> list[str]:
        profile = os.getenv("PIPELINE_PROFILE", "standard")
        profiles = self._raw.get("pipeline", {}).get("profiles", {})
        return profiles.get(profile, profiles.get("standard", {})).get("user_checkpoints", [])

    @property
    def docker_compose_file(self) -> str:
        return self._raw.get("docker", {}).get("compose_file", "docker-compose.local.yml")

    @property
    def docker_api_service(self) -> str:
        return self._raw.get("docker", {}).get("api_service", "api")

    @property
    def docker_web_service(self) -> str:
        return self._raw.get("docker", {}).get("web_service", "web")

    @property
    def docker_health_timeout(self) -> int:
        return self._raw.get("docker", {}).get("health_timeout", 60)

    @property
    def docker_health_interval(self) -> int:
        return self._raw.get("docker", {}).get("health_interval", 2)

    def get_model_for_stage(self, stage: str) -> str:
        routing = self._routing.get("routing", {})
        model_name = routing.get(stage, "analyzer")
        groups = self._routing.get("model_groups", {})
        return groups.get(model_name, {}).get("model", "github_copilot/gpt-4o")

    def get_risk_thresholds(self) -> dict[str, Any]:
        return self._thresholds.get("risk", {})

    def get_coverage_thresholds(self) -> dict[str, Any]:
        return self._thresholds.get("coverage", {})

    def get_impact_config(self) -> dict[str, Any]:
        return self._thresholds.get("impact", {})

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
