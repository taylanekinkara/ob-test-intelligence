from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Query

from app.config import AppConfig
from app.orchestrator import PipelineOrchestrator
from app.web.log_reader import get_recent_logs, get_error_logs, get_token_usage, get_artifact_json

app = FastAPI(title="ob-test-intelligence", version="0.1.0")
config = AppConfig()

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9}
.container{max-width:1200px;margin:0 auto;padding:20px}
h1{color:#58a6ff;margin-bottom:20px;font-size:1.5rem}
h2{color:#58a6ff;margin:16px 0 8px;font-size:1.2rem}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
table{width:100%;border-collapse:collapse;margin:8px 0}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #21262d}
th{background:#161b22;color:#8b949e;font-weight:600}
tr:hover{background:#161b22}
.card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px;margin:8px 0}
.badge{padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}
.badge-green{background:#1b4332;color:#40c057}
.badge-yellow{background:#433500;color:#fab005}
.badge-red{background:#3c1f1f;color:#f85149}
.badge-blue{background:#1a3050;color:#58a6ff}
nav{background:#161b22;border-bottom:1px solid #21262d;padding:12px 20px;display:flex;gap:20px;align-items:center}
nav a{color:#8b949e;font-size:.875rem}
nav a:hover,nav a.active{color:#c9d1d9}
.phase-bar{display:flex;gap:4px;margin:12px 0}
.phase-step{padding:4px 10px;border-radius:4px;font-size:.75rem;background:#21262d;color:#484f58}
.phase-step.done{background:#1b4332;color:#40c057}
.phase-step.current{background:#1a3050;color:#58a6ff;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
#logs{background:#010409;border:1px solid #21262d;border-radius:8px;padding:12px;height:350px;overflow-y:auto;font-family:'Cascadia Code',monospace;font-size:.8rem;margin-top:8px;white-space:pre-wrap;word-break:break-all}
.log-stage{color:#58a6ff;font-weight:600}
.log-llm{color:#a371f7}
.log-error{color:#f85149}
.log-ok{color:#40c057}
.log-dim{color:#484f58}
.log-artifact{color:#3fb950}
.token-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:8px 0}
.token-card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;text-align:center}
.token-value{font-size:1.5rem;font-weight:700;color:#58a6ff}
.token-label{font-size:.75rem;color:#8b949e;margin-top:4px}
"""


def _html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - ob-test-intelligence</title><style>{_CSS}</style></head>
<body>
<nav><a href="/">Tests</a><a href="/settings">Settings</a></nav>
<div class="container">{body}</div></body></html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    orch = PipelineOrchestrator(config)
    tests = orch.list_tests()
    rows = "".join(
        f'<tr><td><a href="/test/{t["task_key"]}">{t["task_key"]}</a></td>'
        f'<td><span class="badge badge-blue">{t.get("current_phase","")}</span></td>'
        f'<td>{t.get("updated_at","")[:19]}</td></tr>'
        for t in tests
    )
    return _html("Tests", f"<h1>Tests</h1><table><tr><th>Task</th><th>Phase</th><th>Updated</th></tr>{rows}</table>")


@app.get("/test/{task_key}", response_class=HTMLResponse)
async def test_detail(task_key: str):
    return _html(task_key, _TASK_PAGE.replace("{TASK_KEY}", task_key))


_TASK_PAGE = """
<h1>{TASK_KEY}</h1>
<div id="status" class="card"><table><tr><th>Property</th><th>Value</th></tr><tr><td>Loading...</td></tr></table></div>
<h2>Token Kullanimi</h2>
<div id="tokens" class="token-grid"></div>
<h2>Test Maddeleri</h2>
<div id="test-items"><span class="log-dim">Bekleniyor...</span></div>
<h2>Loglar</h2>
<div id="logs"></div>
<script>
let lastLine = 0;
const taskId = '{TASK_KEY}';

function renderStatus(data) {
    let phases = '';
    const allPhases = ['ensure_ready','task_read','code_analyze','impact_analyze','test_assess','scenario_generate','env_prepare','test_execute','verify','report'];
    const completed = data.phases_completed || [];
    const current = data.current_phase;
    allPhases.forEach(p => {
        let cls = 'phase-step';
        if (completed.includes(p)) cls += ' done';
        else if (p === current) cls += ' current';
        phases += '<span class="' + cls + '">' + p.replace(/_/g,' ') + '</span>';
    });
    document.getElementById('status').innerHTML =
        '<div class="phase-bar">' + phases + '</div>' +
        '<table><tr><th>Phase</th><td><span class="badge badge-blue">' + current + '</span></td></tr>' +
        '<tr><th>Completed</th><td>' + (completed.join(', ') || 'none') + '</td></tr>' +
        '<tr><th>Created</th><td>' + (data.created_at || '').slice(0,19) + '</td></tr></table>';
}

function renderTokens(data) {
    if (!data.totals) { document.getElementById('tokens').style.display='none'; return; }
    const t = data.totals;
    document.getElementById('tokens').style.display='';
    document.getElementById('tokens').innerHTML =
        '<div class="token-card"><div class="token-value">' + t.total_calls + '</div><div class="token-label">LLM Cagrisi</div></div>' +
        '<div class="token-card"><div class="token-value">' + (t.total_prompt_tokens||0).toLocaleString() + '</div><div class="token-label">Prompt Token</div></div>' +
        '<div class="token-card"><div class="token-value">' + (t.total_completion_tokens||0).toLocaleString() + '</div><div class="token-label">Completion Token</div></div>' +
        '<div class="token-card"><div class="token-value">' + (t.total_tokens||0).toLocaleString() + '</div><div class="token-label">Toplam Token</div></div>';
}

function renderTestItems(data) {
    const a = data.assessment || {};
    const s = data.scenarios || {};
    const items = a.test_items || [];
    const skips = a.skip_items || [];
    const scenarios = s.scenarios || [];

    if (items.length === 0 && skips.length === 0) return;

    let html = '<table><tr><th>#</th><th>Hedef</th><th>Aciklama</th><th>Tip</th><th>Priority</th><th>Senaryolar</th></tr>';
    items.forEach((item, i) => {
        const itemScenarios = scenarios.filter(sc => sc.test_item_id === item.id);
        let scenarioHtml = '';
        if (itemScenarios.length > 0) {
            scenarioHtml = '<table style="margin:0;font-size:.8rem">';
            itemScenarios.forEach(sc => {
                const typeColors = {positive:'#40c057',negative:'#f85149',boundary:'#fab005',regression:'#58a6ff',happy_path:'#40c057',edge_case:'#fab005',error_case:'#f85149'};
                const color = typeColors[sc.type] || '#8b949e';
                scenarioHtml += '<tr><td style="color:' + color + '">' + (sc.name || sc.id) + '</td><td>' + (sc.expected_status_code || '') + '</td></tr>';
            });
            scenarioHtml += '</table>';
        } else {
            scenarioHtml = '<span class="log-dim">-</span>';
        }
        html += '<tr><td>' + item.id + '</td><td><code>' + (item.target||'') + '</code></td><td>' + (item.description||'') + '</td><td><span class="badge badge-blue">' + (item.test_type||'') + '</span></td><td>' + (item.priority||'') + '</td><td>' + scenarioHtml + '</td></tr>';
    });
    html += '</table>';

    if (skips.length > 0) {
        html += '<h3 style="margin-top:12px;color:#484f58">Atlanan</h3><table><tr><th>Hedef</th><th>Sebep</th></tr>';
        skips.forEach(s => {
            html += '<tr><td><code>' + (s.target||'') + '</code></td><td style="color:#8b949e">' + (s.reason||'') + '</td></tr>';
        });
        html += '</table>';
    }

    document.getElementById('test-items').innerHTML = html;
}

function renderLogs(entries) {
    const el = document.getElementById('logs');
    let html = '';
    entries.forEach(e => {
        let cls = 'log-dim';
        if (e.type === 'stage_start' || e.type === 'stage_end') cls = 'log-stage';
        else if (e.type === 'llm') cls = 'log-llm';
        else if (e.type === 'error') cls = 'log-error';
        else if (e.type === 'artifact') cls = 'log-artifact';
        html += '<div class="' + cls + '">' + e.raw + '</div>';
    });
    el.innerHTML = html;
    el.scrollTop = el.scrollHeight;
}

async function refresh() {
    try {
        const r = await fetch('/api/tests/' + taskId);
        if (r.ok) renderStatus(await r.json());
    } catch(e) {}

    try {
        const r2 = await fetch('/api/logs/' + taskId + '?after=' + lastLine);
        if (r2.ok) {
            const data = await r2.json();
            if (data.entries && data.entries.length > 0) {
                renderLogs(data.entries);
                lastLine = data.total_lines;
            }
        }
    } catch(e) {}

    try {
        const r3 = await fetch('/api/tokens/' + taskId);
        if (r3.ok) renderTokens(await r3.json());
    } catch(e) {}

    try {
        const r4 = await fetch('/api/test-items/' + taskId);
        if (r4.ok) renderTestItems(await r4.json());
    } catch(e) {}
}

refresh();
setInterval(refresh, 2000);
</script>
"""


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    body = f"""<h1>Settings</h1><div class="card"><table>
    <tr><td>ob-core</td><td>{config.ob_core_path}</td></tr>
    <tr><td>graphify</td><td>{config.graphify_path}</td></tr>
    <tr><td>context</td><td>{config.context_path}</td></tr>
    <tr><td>port</td><td>{config.port}</td></tr>
    </table></div>"""
    return _html("Settings", body)


@app.get("/api/status")
async def api_status():
    return {"status": "ok"}


@app.get("/api/tests")
async def api_list_tests():
    return {"tests": PipelineOrchestrator(config).list_tests()}


@app.get("/api/tests/{task_key}")
async def api_get_test(task_key: str):
    state = PipelineOrchestrator(config).get_state(task_key)
    if not state:
        return JSONResponse({"error": "not found"}, status_code=404)
    return state.model_dump()


@app.get("/api/logs/{task_key}")
async def api_logs(task_key: str, after: int = Query(0)):
    entries = get_recent_logs(task_key, after_line=after)
    total = after + len(entries)
    return {"entries": entries, "total_lines": total}


@app.get("/api/tokens/{task_key}")
async def api_tokens(task_key: str):
    return get_token_usage(task_key)


@app.get("/api/test-items/{task_key}")
async def api_test_items(task_key: str):
    assessment = get_artifact_json(task_key, "test-assessment.json")
    scenarios = get_artifact_json(task_key, "test-scenarios.json")
    return {"assessment": assessment, "scenarios": scenarios}
