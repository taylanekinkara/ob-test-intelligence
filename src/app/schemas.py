from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

PhaseEnum = Literal[
    "ensure_ready",
    "task_read",
    "code_analyze",
    "impact_analyze",
    "test_assess",
    "scenario_generate",
    "env_prepare",
    "test_execute",
    "verify",
    "report",
]

TestStatusEnum = Literal[
    "pending",
    "running",
    "waiting_user",
    "completed",
    "failed",
    "cancelled",
]

TaskSourceEnum = Literal["jira", "manual", "cli"]


class FileChangeInfo(BaseModel):
    path: str
    layer: str
    domain: str
    change_type: str
    summary: str


class CodeAnalysisResult(BaseModel):
    branch: str
    files_changed: list[FileChangeInfo]
    layers_affected: list[str]
    domains_affected: list[str]
    endpoints_affected: list[dict]


class ImpactNode(BaseModel):
    path: str
    type: str
    risk: str


class ImpactAnalysisResult(BaseModel):
    seed_files: list[str]
    one_hop: dict
    two_hop: dict
    communities_affected: list[dict]
    god_nodes_affected: list
    overall_risk: str
    regression_areas: list[str]


class TestItem(BaseModel):
    id: str
    target: str
    test_type: str
    priority: str
    reason: str
    layer: str
    domain: str
    risk: str


class TestAssessment(BaseModel):
    needs_testing: bool
    test_items: list[TestItem]
    skip_items: list[dict]
    environment: dict


class TestStep(BaseModel):
    action: str
    method: str = ""
    url: str = ""
    headers: dict = {}
    body: Any = None


class Assertion(BaseModel):
    field: str
    operator: str
    value: Any = None


class TestScenario(BaseModel):
    id: str
    test_item_id: str
    name: str
    type: str
    steps: list[TestStep]
    assertions: list[Assertion]
    expected_status_code: int = 200


class AssertionResult(BaseModel):
    field: str
    expected: Any
    actual: Any
    passed: bool
    reason: str = ""


class ScenarioResult(BaseModel):
    scenario_id: str
    name: str
    passed: bool
    status_code: int = 0
    assertions: list[AssertionResult]
    duration_ms: int = 0


class TestResult(BaseModel):
    execution_time: str
    total_scenarios: int
    passed: int
    failed: int
    skipped: int
    results: list[ScenarioResult]


class Finding(BaseModel):
    severity: str
    type: str
    description: str
    affected_scenario: str = ""
    recommendation: str = ""


class VerificationReport(BaseModel):
    overall_verdict: str
    coverage_percentage: float
    test_quality: str
    findings: list[Finding]
    false_positives: list
    false_negatives: list[dict]


class PipelineState(BaseModel):
    task_key: str
    task_source: TaskSourceEnum
    current_phase: PhaseEnum
    phases_completed: list[PhaseEnum]
    project_path: str
    config: dict
    artifacts: dict = {}
    created_at: str = ""
    updated_at: str = ""
