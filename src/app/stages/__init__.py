from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import AppConfig
    from app.orchestrator import PipelineOrchestrator


def register_all(orch: "PipelineOrchestrator", config: "AppConfig") -> None:
    from app.stages.ensure_ready import stage_ensure_ready
    from app.stages.task_read import stage_task_read
    from app.stages.code_analyze import stage_code_analyze
    from app.stages.impact_analyze import stage_impact_analyze
    from app.stages.test_assess import stage_test_assess
    from app.stages.scenario_generate import stage_scenario_generate
    from app.stages.env_prepare import stage_env_prepare
    from app.stages.test_execute import stage_test_execute
    from app.stages.verify import stage_verify
    from app.stages.report import stage_report

    orch.register_stage("ensure_ready", stage_ensure_ready)
    orch.register_stage("task_read", stage_task_read)
    orch.register_stage("code_analyze", stage_code_analyze)
    orch.register_stage("impact_analyze", stage_impact_analyze)
    orch.register_stage("test_assess", stage_test_assess)
    orch.register_stage("scenario_generate", stage_scenario_generate)
    orch.register_stage("env_prepare", stage_env_prepare)
    orch.register_stage("test_execute", stage_test_execute)
    orch.register_stage("verify", stage_verify)
    orch.register_stage("report", stage_report)
