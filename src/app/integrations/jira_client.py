from __future__ import annotations

from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class JiraClient:
    def __init__(self) -> None:
        pass

    async def get_issue(self, issue_key: str, **kwargs) -> dict[str, Any]:
        logger.info("jira_stub_note", key=issue_key, hint="MCP ile jira-raw.json olusturulmali")
        return {"key": issue_key, "fields": {}}

    async def get_comments(self, issue_key: str, **kwargs) -> list[dict]:
        return []

    async def get_dev_info(self, issue_key: str, **kwargs) -> dict[str, Any]:
        return {"branches": [], "pullRequests": []}
