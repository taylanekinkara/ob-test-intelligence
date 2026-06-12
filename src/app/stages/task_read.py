from __future__ import annotations


import json
import re
from pathlib import Path

from app.config import AppConfig
from app.integrations.litellm_client import LiteLLMClient
from app.utils.context_loader import ContextLoader
from app.utils.files import write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)

_DOMAIN_KEYWORDS = {
    "bus": ["bus", "sefer", "biniş", "journey", "otobüs"],
    "flight": ["flight", "uçak", "hava", "ucak"],
    "hotel": ["hotel", "otel", "konaklama"],
    "sea": ["sea", "deniz", "ferry", "vapur", "gemi"],
    "payment": ["payment", "ödeme", "pos", "refund", "kupon"],
    "rentacar": ["rentacar", "araç", "rent a car"],
    "transfer": ["transfer"],
}


def _parse_json_response(text: str) -> dict:
    cb_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if cb_match:
        try:
            return json.loads(cb_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}
        return {}


def _detect_domain(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return domain
    return "unknown"


def _extract_text_from_adf(node: dict | list | str) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_extract_text_from_adf(item) for item in node)
    if isinstance(node, dict):
        content = node.get("content", [])
        text = node.get("text", "")
        return (_extract_text_from_adf(content) + " " + text).strip()
    return ""


def _load_jira_raw(output_dir: Path, task_key: str) -> dict:
    jira_file = output_dir / "jira-raw.json"
    if jira_file.exists():
        return json.loads(jira_file.read_text(encoding="utf-8"))
    logger.warning("jira_raw_not_found", key=task_key)
    return {}


async def stage_task_read(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    jira_data = _load_jira_raw(output_dir, task_key)
    issue = jira_data.get("issue", {})
    comments = jira_data.get("comments", [])
    dev_info = jira_data.get("dev_info", {})

    if not issue:
        logger.info("jira_no_mcp_data_using_stub", key=task_key)
        issue = {"key": task_key, "fields": {}}

    fields = issue.get("fields", {}) or {}
    title = fields.get("summary", "") if isinstance(fields, dict) else ""
    description = fields.get("description", "") if isinstance(fields, dict) else ""
    if isinstance(description, dict):
        description = _extract_text_from_adf(description)
    elif description is None:
        description = ""

    domain = _detect_domain(title, description or "")

    branches_raw = dev_info.get("branches", [])
    prs = dev_info.get("pullRequests", [])
    branch = ""
    if branches_raw:
        b = branches_raw[0]
        if isinstance(b, dict):
            branch = b.get("name", b.get("refName", ""))
        elif isinstance(b, str):
            branch = b
    if not branch and prs:
        pr = prs[0] if isinstance(prs[0], dict) else {}
        branch = pr.get("headRefName", pr.get("branch", ""))

    context_loader = ContextLoader(config.context_path)
    domain_context = context_loader.load_for_phase("task_read", domain)

    comments_text = "\n".join(
        c.get("body", "") if isinstance(c, dict) else str(c)
        for c in comments
    )

    parsed = {}
    try:
        prompt_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "task_analyzer.md"
        prompt_template = prompt_path.read_text(encoding="utf-8")

        prompt = prompt_template.format(
            task_key=task_key,
            title=title,
            description=str(description or "")[:6000],
            comments=comments_text[:3000],
            domain=domain,
            branch=branch,
            domain_context=domain_context,
        )

        llm = LiteLLMClient(config, task_key=task_key, phase="task_read")
        model = config.get_model_for_stage("task_analyze")
        response = await llm.complete(model, messages=[{"role": "user", "content": prompt}])
        parsed = _parse_json_response(response)
    except Exception as e:
        log_error(task_key, "stage_task_read", e, output_dir)
        logger.warning("task_read_llm_fallback", error=str(e))

    summary = {
        "task_key": task_key,
        "title": title,
        "description_summary": parsed.get("description_summary", ""),
        "domain": parsed.get("domain", domain),
        "affected_verticals": parsed.get("affected_verticals", []),
        "what_changed": parsed.get("what_changed", ""),
        "expected_behavior": parsed.get("expected_behavior", ""),
        "acceptance_criteria": parsed.get("acceptance_criteria", []),
        "branch": branch,
        "risk_level": parsed.get("risk_level", "low"),
        "relevant_context_files": parsed.get("relevant_context_files", []),
    }

    write_json(output_dir / "task-summary.json", summary)
    logger.info("task_read_complete", task_key=task_key, domain=summary["domain"])
    return {"task_summary": summary}
