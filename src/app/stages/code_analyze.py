from __future__ import annotations


import json
import re
from pathlib import Path

from app.config import AppConfig
from app.integrations.git_client import GitClient
from app.integrations.litellm_client import LiteLLMClient
from app.utils.context_loader import ContextLoader
from app.utils.files import write_json
from app.utils.layer_classifier import classify_layer
from app.utils.domain_classifier import classify_domain
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


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


async def stage_code_analyze(state) -> dict:
    config = AppConfig()
    task_key = state.task_key

    output_dir = config.outputs_path / task_key

    task_summary_path = output_dir / "task-summary.json"
    branch = ""
    domain = ""
    if task_summary_path.exists():
        ts = json.loads(task_summary_path.read_text(encoding="utf-8"))
        branch = ts.get("branch", "")
        domain = ts.get("domain", "")

    git = GitClient(config)
    if not branch:
        try:
            branch = await git.current_branch()
        except Exception:
            branch = "main"

    files_changed = await git.diff_files(branch) if branch else []
    diff_text = ""
    try:
        diff_text = await git.diff_content(branch) if branch else ""
    except Exception:
        pass

    context_loader = ContextLoader(config.context_path)
    arch_context = context_loader.load_for_phase("code_analyze")

    files_info = []
    for fp in files_changed:
        files_info.append({
            "path": fp,
            "layer": classify_layer(fp),
            "domain": classify_domain(fp),
            "change_type": _detect_change_type(fp),
            "summary": "",
        })

    analysis_map = {}
    endpoints_affected = []
    llm_summary = ""

    try:
        prompt_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts" / "code_analyzer.md"
        prompt_template = prompt_path.read_text(encoding="utf-8")

        max_files = 200
        truncated_files = files_info[:max_files]
        files_desc = json.dumps(truncated_files, indent=2, ensure_ascii=False)
        if len(files_info) > max_files:
            files_desc += f"\n... and {len(files_info) - max_files} more files"

        max_diff = 30000
        diff_chunk = diff_text[:max_diff]
        if len(diff_text) > max_diff:
            diff_chunk += f"\n... truncated ({len(diff_text)} total chars)"

        max_arch = 20000
        arch_chunk = arch_context[:max_arch]
        if len(arch_context) > max_arch:
            arch_chunk += f"\n... truncated ({len(arch_context)} total chars)"

        prompt = prompt_template.format(
            branch=branch,
            files_changed=files_desc,
            diff_content=diff_chunk,
            architecture_context=arch_chunk,
            domain=domain,
        )

        llm = LiteLLMClient(config, task_key=task_key, phase="code_analyze")
        model = config.get_model_for_stage("code_analyze")
        response = await llm.complete(model, messages=[{"role": "user", "content": prompt}], max_tokens=8192)

        parsed = _parse_json_response(response)
        llm_file_analyses = parsed.get("files", [])

        for fa in llm_file_analyses:
            analysis_map[fa.get("path", "")] = fa

        endpoints_affected = parsed.get("endpoints_affected", [])
        llm_summary = parsed.get("summary", "")
    except Exception as e:
        log_error(task_key, "stage_code_analyze", e, output_dir)
        logger.warning("code_analyze_llm_fallback", error=str(e))

    for fi in files_info:
        fa = analysis_map.get(fi["path"], {})
        if fa.get("layer"):
            fi["layer"] = fa["layer"]
        if fa.get("domain"):
            fi["domain"] = fa["domain"]
        if fa.get("change_type"):
            fi["change_type"] = fa["change_type"]
        if fa.get("summary"):
            fi["summary"] = fa["summary"]

    result = {
        "branch": branch,
        "files_changed": files_info,
        "layers_affected": list(set(f["layer"] for f in files_info if f["layer"] != "unknown")),
        "domains_affected": list(set(f["domain"] for f in files_info if f["domain"] != "unknown")),
        "endpoints_affected": endpoints_affected,
        "llm_summary": llm_summary,
    }

    write_json(output_dir / "code-analysis.json", result)
    logger.info("code_analyze_complete", task_key=task_key, files=len(files_info))
    return {"code_analysis": result}


def _detect_change_type(file_path: str) -> str:
    fp = file_path.lower()
    if "controller" in fp:
        return "api_change"
    if "service" in fp:
        return "service_logic"
    if "entity" in fp or "model" in fp:
        return "model_change"
    if "view" in fp or "page" in fp or "component" in fp:
        return "ui_change"
    return "unknown"
