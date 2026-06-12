from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import AppConfig
from app.schemas import PipelineState
from app.utils.logging import (
    get_logger,
    log_artifact,
    log_error,
    log_stage_end,
    log_stage_start,
    setup_task_logging,
)
from app.utils.files import read_json

logger = get_logger(__name__)


class PipelineOrchestrator:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self._stages: dict[str, Callable] = {}
        self._event_callbacks: list[Callable] = []
        self._state: PipelineState | None = None

    def register_stage(self, phase: str, handler: Callable) -> None:
        self._stages[phase] = handler

    def on_event(self, callback: Callable) -> None:
        self._event_callbacks.append(callback)

    def _emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        payload = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        if self._state:
            payload["task_key"] = self._state.task_key
            payload["phase"] = self._state.current_phase
        for cb in self._event_callbacks:
            try:
                cb(payload)
            except Exception:
                pass

    def _init_state(self, task_key: str, task_source: str = "jira", project_path: str = "") -> PipelineState:
        now = datetime.now(timezone.utc).isoformat()
        state = PipelineState(
            task_key=task_key,
            task_source=task_source,
            current_phase="ensure_ready",
            phases_completed=[],
            project_path=project_path or str(self.config.ob_core_path),
            config={
                "graphify_path": str(self.config.graphify_path),
                "context_path": str(self.config.context_path),
                "ob_core_path": str(self.config.ob_core_path),
                "api_port": self.config.api_port,
                "web_port": self.config.port,
                "llm_profile": self.config.llm_profile,
            },
            artifacts={
                "task_summary": "",
                "code_analysis": "",
                "impact_analysis": "",
                "test_assessment": "",
                "test_scenarios": "",
                "test_results": "",
                "verification_report": "",
            },
            created_at=now,
            updated_at=now,
        )
        self._state = state

        output_dir = self.config.outputs_path / task_key
        setup_task_logging(task_key, output_dir)

        self._save_state()
        return state

    def _save_state(self) -> None:
        if not self._state:
            return
        output_dir = self.config.outputs_path / self._state.task_key
        output_dir.mkdir(parents=True, exist_ok=True)
        state_path = output_dir / "state.json"
        state_path.write_text(self._state.model_dump_json(indent=2), encoding="utf-8")

    def _load_state(self, task_key: str) -> PipelineState | None:
        state_path = self.config.outputs_path / task_key / "state.json"
        if not state_path.exists():
            return None
        data = json.loads(state_path.read_text(encoding="utf-8"))
        self._state = PipelineState(**data)

        output_dir = self.config.outputs_path / task_key
        setup_task_logging(task_key, output_dir)

        return self._state

    def _advance_phase(self) -> str | None:
        phases = self.config.pipeline_phases
        if not self._state:
            return None
        current = self._state.current_phase
        try:
            idx = phases.index(current)
        except ValueError:
            return None
        if current not in self._state.phases_completed:
            self._state.phases_completed.append(current)
        if idx + 1 < len(phases):
            next_phase = phases[idx + 1]
            self._state.current_phase = next_phase
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_state()
            return next_phase
        return None

    def _is_user_checkpoint(self, phase: str) -> bool:
        return phase in self.config.user_checkpoints

    def _run_stage(self, phase: str) -> dict | None:
        task_key = self._state.task_key
        output_dir = self.config.outputs_path / task_key

        log_stage_start(task_key, phase, output_dir)
        start_time = time.time()

        handler = self._stages.get(phase)
        result = None
        success = True

        if handler:
            try:
                result = handler(self._state)
                import asyncio
                if asyncio.iscoroutine(result) or hasattr(result, '__await__'):
                    result = asyncio.get_event_loop().run_until_complete(result) if asyncio.get_event_loop().is_running() else None
            except Exception as e:
                success = False
                tb = traceback.format_exc()
                log_error(task_key, phase, e, output_dir)
                logger.error("phase_failed", phase=phase, error=str(e), traceback=tb)
                self._emit("phase_failed", {"phase": phase, "error": str(e), "traceback": tb})
                raise

        duration_ms = int((time.time() - start_time) * 1000)
        log_stage_end(task_key, phase, output_dir, duration_ms, success)

        if result and isinstance(result, dict):
            for key in self._state.artifacts:
                if key and key in str(result):
                    artifact_path = output_dir / f"{key.replace('_', '-')}.json"
                    if artifact_path.exists():
                        log_artifact(task_key, key, artifact_path, artifact_path.stat().st_size)
                    break

        return result

    async def run(self, task_key: str, task_source: str = "jira", project_path: str = "") -> PipelineState:
        state = self._init_state(task_key, task_source, project_path)
        self._emit("pipeline_started", {"task_key": task_key})

        phases = self.config.pipeline_phases
        for phase in phases:
            if not self._state:
                break

            self._state.current_phase = phase
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_state()
            self._emit("phase_started", {"phase": phase})

            output_dir = self.config.outputs_path / task_key
            start_time = time.time()

            handler = self._stages.get(phase)
            if handler:
                try:
                    result = await handler(self._state)
                    if result and isinstance(result, dict):
                        artifact_key = phase.replace("ensure_ready", "").replace("_", "")
                        for key in self._state.artifacts:
                            if key and key in str(result):
                                self._state.artifacts[key] = json.dumps(result.get(key, ""), ensure_ascii=False)
                                break
                except Exception as e:
                    tb = traceback.format_exc()
                    duration_ms = int((time.time() - start_time) * 1000)
                    log_stage_start(task_key, phase, output_dir)
                    log_error(task_key, phase, e, output_dir)
                    log_stage_end(task_key, phase, output_dir, duration_ms, success=False)
                    logger.error("phase_failed", phase=phase, error=str(e))
                    self._emit("phase_failed", {"phase": phase, "error": str(e), "traceback": tb})
                    raise

            duration_ms = int((time.time() - start_time) * 1000)
            log_stage_start(task_key, phase, output_dir)
            log_stage_end(task_key, phase, output_dir, duration_ms)

            self._emit("phase_completed", {"phase": phase})
            if phase not in self._state.phases_completed:
                self._state.phases_completed.append(phase)

            if self._is_user_checkpoint(phase):
                self._emit("waiting_for_user", {"phase": phase})
                self._state.updated_at = datetime.now(timezone.utc).isoformat()
                self._save_state()
                return self._state

        if self._state:
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_state()
        self._emit("pipeline_completed", {"task_key": task_key})
        return self._state

    async def resume(self, task_key: str, user_response: str = "approve") -> PipelineState:
        state = self._load_state(task_key)
        if not state:
            raise ValueError(f"No state found for {task_key}")

        self._state = state
        current = state.current_phase
        self._emit("user_response_received", {"phase": current, "response": user_response})

        next_phase = self._advance_phase()
        if not next_phase:
            self._emit("pipeline_completed", {"task_key": task_key})
            return self._state

        phases = self.config.pipeline_phases
        remaining = phases[phases.index(next_phase):]

        for phase in remaining:
            if not self._state:
                break

            self._state.current_phase = phase
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_state()
            self._emit("phase_started", {"phase": phase})

            output_dir = self.config.outputs_path / task_key
            log_stage_start(task_key, phase, output_dir)
            start_time = time.time()

            handler = self._stages.get(phase)
            if handler:
                try:
                    result = await handler(self._state)
                except Exception as e:
                    tb = traceback.format_exc()
                    duration_ms = int((time.time() - start_time) * 1000)
                    log_error(task_key, phase, e, output_dir)
                    log_stage_end(task_key, phase, output_dir, duration_ms, success=False)
                    logger.error("phase_failed", phase=phase, error=str(e))
                    self._emit("phase_failed", {"phase": phase, "error": str(e), "traceback": tb})
                    raise

            duration_ms = int((time.time() - start_time) * 1000)
            log_stage_end(task_key, phase, output_dir, duration_ms)

            self._emit("phase_completed", {"phase": phase})
            if phase not in self._state.phases_completed:
                self._state.phases_completed.append(phase)

            if self._is_user_checkpoint(phase):
                self._emit("waiting_for_user", {"phase": phase})
                self._state.updated_at = datetime.now(timezone.utc).isoformat()
                self._save_state()
                return self._state

        if self._state:
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_state()
        self._emit("pipeline_completed", {"task_key": task_key})
        return self._state

    def get_state(self, task_key: str) -> PipelineState | None:
        return self._load_state(task_key)

    def list_tests(self) -> list[dict[str, Any]]:
        tests = []
        outputs = self.config.outputs_path
        if not outputs.exists():
            return tests
        for task_dir in sorted(outputs.iterdir()):
            state_file = task_dir / "state.json"
            if state_file.exists():
                data = json.loads(state_file.read_text(encoding="utf-8"))
                tests.append(data)
        return tests
