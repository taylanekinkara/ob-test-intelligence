from __future__ import annotations

import json
import pytest
from pathlib import Path
from app.schemas import PipelineState
from app.orchestrator import PipelineOrchestrator


@pytest.fixture
def config(tmp_path, monkeypatch):
    outputs = tmp_path / "outputs" / "tests"
    outputs.mkdir(parents=True)

    monkeypatch.setenv("OB_CORE_PATH", str(tmp_path / "core"))
    monkeypatch.setenv("GRAPHIFY_PATH", str(tmp_path / "graphify"))
    monkeypatch.setenv("CONTEXT_PATH", str(tmp_path / "context"))
    monkeypatch.setenv("WEB_PORT", "8081")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")

    from app.config import AppConfig
    AppConfig.reset()
    config = AppConfig()
    config._raw["paths"]["outputs"] = str(outputs)
    return config


def test_init_state(config):
    orch = PipelineOrchestrator(config)
    state = orch._init_state("TEST-001", "manual")
    assert state.task_key == "TEST-001"
    assert state.current_phase == "ensure_ready"
    assert state.phases_completed == []


def test_save_and_load_state(config):
    orch = PipelineOrchestrator(config)
    state = orch._init_state("TEST-002", "jira")
    loaded = orch._load_state("TEST-002")
    assert loaded is not None
    assert loaded.task_key == "TEST-002"


def test_advance_phase(config):
    orch = PipelineOrchestrator(config)
    state = orch._init_state("TEST-003")
    next_phase = orch._advance_phase()
    assert next_phase is not None
    assert "ensure_ready" in state.phases_completed


def test_list_tests(config):
    orch = PipelineOrchestrator(config)
    orch._init_state("TEST-004")
    orch._init_state("TEST-005")
    tests = orch.list_tests()
    assert len(tests) == 2
