from __future__ import annotations

from pathlib import Path


class ContextLoader:
    def __init__(self, context_path: str | Path) -> None:
        self.context_path = Path(context_path)

    def load_for_phase(self, phase: str, domain: str = "") -> str:
        docs = []

        if phase in ("task_read", "test_assess", "verify"):
            docs.append(self._read("prd.md"))
            docs.append(self._read("glossary.md"))

        if phase == "code_analyze":
            docs.append(self._read("architecture.md"))
            docs.append(self._read("conventions.md"))

        if phase in ("scenario_generate", "test_execute"):
            if domain:
                docs.append(self._read(f"domain/{domain}.md"))
            docs.append(self._read("infrastructure/api-pipeline.md"))

        if domain and phase in ("task_read", "impact_assess"):
            docs.append(self._read(f"domain/{domain}.md"))

        return "\n\n---\n\n".join(d for d in docs if d)

    def _read(self, relative_path: str) -> str:
        path = self.context_path / relative_path
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def list_available(self) -> list[str]:
        if not self.context_path.exists():
            return []
        return [
            str(p.relative_to(self.context_path)).replace("\\", "/")
            for p in self.context_path.rglob("*.md")
        ]
