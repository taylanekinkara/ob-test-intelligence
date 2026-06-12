from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_CANDIDATES = ["preprod", "stage"]
_MAX_COMMITS = 50


class GitClient:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.repo_path = self.config.ob_core_path

    async def diff_files(self, branch: str, base: str = "") -> list[str]:
        if not branch:
            return []
        if not await self.branch_exists(branch):
            return []
        resolved_base = base or await self._find_base(branch)
        if not resolved_base or resolved_base == branch:
            return []
        cmd = ["git", "-C", str(self.repo_path), "diff", f"{resolved_base}...{branch}", "--name-only"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []
        return [line.strip() for line in stdout.decode().splitlines() if line.strip()]

    async def diff_content(self, branch: str, base: str = "", max_chars: int = 50000) -> str:
        if not branch:
            return ""
        if not await self.branch_exists(branch):
            return ""
        resolved_base = base or await self._find_base(branch)
        if not resolved_base or resolved_base == branch:
            return ""
        cmd = ["git", "-C", str(self.repo_path), "diff", f"{resolved_base}...{branch}", "-U2", "."]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        text = stdout.decode(errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... truncated ({len(text)} total chars)"
        return text

    async def current_branch(self) -> str:
        cmd = ["git", "-C", str(self.repo_path), "branch", "--show-current"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def branch_exists(self, branch: str) -> bool:
        cmd = ["git", "-C", str(self.repo_path), "rev-parse", "--verify", branch]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    async def _count_commits(self, base: str, branch: str) -> int:
        cmd = ["git", "-C", str(self.repo_path), "rev-list", "--count", f"{base}..{branch}"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return 999999
        try:
            return int(stdout.decode().strip())
        except ValueError:
            return 999999

    async def _find_base(self, branch: str) -> str:
        for candidate in _BASE_CANDIDATES:
            if not await self.branch_exists(candidate):
                continue
            if candidate == branch:
                continue
            count = await self._count_commits(candidate, branch)
            if 0 < count <= _MAX_COMMITS:
                logger.info("git_base_found", branch=branch, base=candidate, commits=count)
                return candidate
        for candidate in _BASE_CANDIDATES:
            if not await self.branch_exists(candidate):
                continue
            if candidate == branch:
                continue
            return candidate
        return ""
