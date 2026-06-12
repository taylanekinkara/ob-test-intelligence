from __future__ import annotations


from datetime import datetime

from app.config import AppConfig
from app.utils.files import read_json, write_text, write_json
from app.utils.logging import get_logger, log_error

logger = get_logger(__name__)


async def stage_report(state) -> dict:
    config = AppConfig()
    task_key = state.task_key
    output_dir = config.outputs_path / task_key

    try:
        return await _stage_report_inner(state, config, task_key, output_dir)
    except Exception as e:
        log_error(task_key, "stage_report", e, output_dir)
        logger.error("report_failed", task_key=task_key, error=str(e))
        raise


async def _stage_report_inner(state, config: AppConfig, task_key: str, output_dir: Path) -> dict:

    task_summary = read_json(output_dir / "task-summary.json") or {}
    code_analysis = read_json(output_dir / "code-analysis.json") or {}
    impact_analysis = read_json(output_dir / "impact-analysis.json") or {}
    test_results = read_json(output_dir / "test-results.json") or {}
    verification = read_json(output_dir / "verification-report.json") or {}
    env_status = read_json(output_dir / "env-status.json") or {}

    title = task_summary.get("title", task_key)
    verdict = verification.get("overall_verdict", "UNKNOWN")
    coverage = verification.get("coverage_percentage", 0)
    total = test_results.get("total_scenarios", 0)
    passed = test_results.get("passed", 0)
    failed = test_results.get("failed", 0)
    skipped = test_results.get("skipped", 0)
    note = test_results.get("note", "")

    verdict_icon = {"PASS": "✅", "PASS_WITH_NOTES": "⚠️", "FAIL": "❌", "SKIPPED": "⏭️"}.get(verdict, "?")

    if skipped > 0 and failed == 0 and passed == 0:
        verdict_display = "⏭️ SKIPPED"
        coverage_display = "N/A"
        scenarios_display = f"{skipped} senaryo kaydedildi (calistirilmadi)"
    else:
        verdict_display = f"{verdict_icon} {verdict}"
        coverage_display = f"{coverage}%"
        scenarios_display = f"{passed}/{total} senaryo ({failed} basarisiz)"

    md = f"""# Test Report: {task_key}

## Ozet

| Alan | Deger |
|------|-------|
| Task | {title} |
| Sonuc | {verdict_display} |
| Coverage | {coverage_display} |
| Gecen/Kalan | {scenarios_display} |
| Risk | {impact_analysis.get('overall_risk', 'N/A')} |
| Domain | {task_summary.get('domain', 'N/A')} |
| Branch | {code_analysis.get('branch', 'N/A')} |
"""

    if note:
        md += f"\n> **Not:** {note}\n"

    md += """
## Degisen Dosyalar

| Dosya | Katman | Domain | Degisiklik Turu |
|-------|--------|--------|-----------------|
"""
    for f in code_analysis.get("files_changed", []):
        md += f"| `{f.get('path', '')}` | {f.get('layer', '')} | {f.get('domain', '')} | {f.get('change_type', '')} |\n"

    md += f"""
## Etki Analizi

| Metrik | Deger |
|--------|-------|
| 1-hop etkilenen | {impact_analysis.get('one_hop', {}).get('count', 0)} dosya |
| 2-hop etkilenen | {impact_analysis.get('two_hop', {}).get('count', 0)} dosya |
| Genel risk | {impact_analysis.get('overall_risk', 'N/A')} |
| Regresyon alanlari | {', '.join(str(r) for r in impact_analysis.get('regression_areas', [])) or 'Yok'} |

## Test Senaryolari

| ID | Ad | Tur | Sonuc | Sure |
|----|-----|------|-------|------|
"""
    for r in test_results.get("results", []):
        if r.get("error", "").startswith("skipped"):
            status = "⏭️ SKIP"
        elif r["passed"]:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        scenarios_data = read_json(output_dir / "test-scenarios.json") or {}
        scenario_type = ""
        for s in scenarios_data.get("scenarios", []):
            if s["id"] == r["scenario_id"]:
                scenario_type = s.get("type", "")
                break
        md += f"| {r['scenario_id']} | {r.get('name', '')} | {scenario_type} | {status} | {r.get('duration_ms', 0)}ms |\n"

    findings = verification.get("findings", [])
    if findings:
        md += "\n## Bulgular\n\n"
        for f in findings:
            severity = f.get("severity", "").upper()
            md += f"- **[{severity}]** {f.get('description', '')}\n"
            if f.get("recommendation"):
                md += f"  - Oneri: {f['recommendation']}\n"

    false_neg = verification.get("false_negatives", [])
    if false_neg:
        md += "\n## False Negatives\n\n"
        for fn in false_neg:
            md += f"- `{fn.get('scenario', '')}` - {fn.get('reason', '')}: {fn.get('detail', '')}\n"

    md += f"""
## Ortam

| Bilesen | Deger |
|---------|-------|
| API | {env_status.get('api_url', 'N/A')} - {'Saglikli' if env_status.get('api_healthy') else 'Sagliksiz'} |
| Web | {env_status.get('web_url', 'N/A')} - {'Saglikli' if env_status.get('web_healthy') else 'Sagliksiz'} |
| Docker | {'Kullanildi' if env_status.get('api_healthy') else 'Kullanilmadi'} |
"""

    token_usage = read_json(output_dir / "token-usage.json") or {}
    token_totals = token_usage.get("totals", {})
    if token_totals:
        md += f"""
## Token Kullanimi

| Metrik | Deger |
|--------|-------|
| Toplam LLM cagrisi | {token_totals.get('total_calls', 0)} |
| Prompt token | {token_totals.get('total_prompt_tokens', 0):,} |
| Completion token | {token_totals.get('total_completion_tokens', 0):,} |
| Toplam token | {token_totals.get('total_tokens', 0):,} |
"""

    md += f"""
---
*Rapor olusturulma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*ob-test-intelligence v0.1.0*
"""

    write_text(output_dir / "report.md", md)

    report_result = {
        "path": str(output_dir / "report.md"),
        "verdict": verdict,
        "coverage": coverage,
        "total": total,
        "passed": passed,
        "failed": failed,
    }
    write_json(output_dir / "report-meta.json", report_result)

    logger.info("report_complete", task_key=task_key, verdict=verdict)
    return {"report": report_result}
