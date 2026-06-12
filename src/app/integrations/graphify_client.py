from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GraphifyClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.graphify_path = self.config.graphify_path

    async def impact_query(self, files: list[str], depth: int = 2) -> dict[str, Any]:
        script = self.graphify_path / "impact-query.js"
        if not script.exists():
            logger.warning("graphify_script_not_found", path=str(script))
            return self._empty_result("script not found")

        files_arg = ",".join(files)
        cmd = ["node", str(script), files_arg, "--depth", str(depth), "--format", "json"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error("graphify_failed", stderr=stderr.decode()[:500])
            return self._empty_result(stderr.decode()[:200])

        try:
            raw = json.loads(stdout.decode())
        except json.JSONDecodeError:
            logger.error("graphify_parse_error", output=stdout.decode()[:500])
            return self._empty_result("parse error")

        return self._normalize(raw, files)

    def _normalize(self, raw: dict, seed_files: list[str]) -> dict[str, Any]:
        summary = raw.get("summary", {})
        impacts = raw.get("impacts", {})
        raw_communities = raw.get("communities", {})

        direct = impacts.get("direct", [])
        one_hop_files = []
        if isinstance(direct, list):
            one_hop_files = list({n.get("file", "") for n in direct if n.get("file")})

        communities = []
        if isinstance(raw_communities, dict):
            for cid, cdata in raw_communities.items():
                if isinstance(cdata, dict):
                    communities.append({
                        "id": cid,
                        "name": cdata.get("name", f"Community {cid}"),
                        "node_count": cdata.get("node_count", 0),
                    })

        return {
            "seed_files": seed_files,
            "one_hop": {"count": len(one_hop_files), "files": one_hop_files},
            "two_hop": {"count": 0, "highlights": []},
            "communities": communities,
            "god_nodes": [],
            "summary": summary,
            "total_affected_nodes": summary.get("total_affected_nodes", 0),
            "relations": summary.get("relations", {}),
        }

    def _empty_result(self, error: str) -> dict[str, Any]:
        return {
            "one_hop": {"count": 0, "files": []},
            "two_hop": {"count": 0, "highlights": []},
            "communities": [],
            "god_nodes": [],
            "error": error,
        }

    def graph_exists(self) -> bool:
        return (self.graphify_path / "graph.json").exists()
