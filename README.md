# ob-test-intelligence

oBilet Core V2 icin AI destekli otomatik test senaryosu uretim, calistirma ve dogrulama araci.

## Mimari

```
Kullanici (opencode / CLI / Web UI)
    |
    v
Skill (SKILL.md) / CLI (ob_test_run.py)
    | subprocess / HTTP API
    v
FastAPI Web Server (:8081) — Pipeline API + Web UI + SSE
    |
    +-- Background Thread — Pipeline orchestrator (10 faz)
    |       +-- LiteLLM Proxy (:4000) — github_copilot/gpt-4o
    |
    +-- Graphify — Impact analysis
    +-- Playwright — Web UI test
    +-- obiletcontext — Domain knowledge
```

## Hizli Baslangic

### 1. Kurulum

```powershell
# Repoyu clone'la
cd C:\repos
git clone <repo-url> ob-test-intelligence
cd ob-test-intelligence

# Otomatik kurulum
.\scripts\win\setup.ps1
```

Elle kurulum:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# .env dosyasini duzenle (gerekiyorsa)
```

### 2. LiteLLM Proxy

```powershell
# Proxy baslat (GitHub Copilot OAuth - API key gerektirmez)
python scripts/start_proxy.py
```

Ilk calistirmada GitHub Copilot device flow baslar. Tarayicida autenticate ol.

### 3. Test Baslat

**CLI ile:**
```powershell
python scripts/ob_test_run.py launch PDB-12345
```

**Web UI ile:**
```powershell
python scripts/ob_test_run.py web
# Tarayicida http://localhost:8081 ac
# Dashboard'dan task key gir ve "Launch Test" tikla
```

**opencode skill ile:**
```
test PDB-12345
```

## Pipeline Fazlari

```
ENSURE_READY → TASK_READ → CODE_ANALYZE → IMPACT_ANALYZE → [USER] →
TEST_ASSESS → SCENARIO_GENERATE → [USER] → ENV_PREPARE → TEST_EXECUTE → VERIFY → REPORT
```

| Faz | Ne Yapar | Kullanici Onayi |
|-----|----------|-----------------|
| ensure_ready | Altyapiyi kontrol et, eksikse kur | Hayir |
| task_read | Jira'dan task'i oku, domain tespit et | Hayir |
| code_analyze | Git diff'ten degisen dosyalari analiz et | Hayir |
| impact_analyze | Graphify ile etki alani tespit et | Hayir |
| test_assess | Test gerekip gerekmedigini degerlendir | **EVET** |
| scenario_generate | Her test maddesi icin senaryo uret | **EVET** |
| env_prepare | Docker ortamini ayaklandir | Hayir |
| test_execute | HTTP/Web testleri calistir | Hayir |
| verify | Sonuclari dogrula, false positive/negative analizi | Hayir |
| report | Tam rapor olustur | Hayir |

## CLI Komutlari

```powershell
# Test baslat
python scripts/ob_test_run.py launch PDB-12345

# Durum sorgula
python scripts/ob_test_run.py poll PDB-12345

# Kullanici onayi ile devam et
python scripts/ob_test_run.py resume PDB-12345 --response approve

# Tum testleri listele
python scripts/ob_test_run.py status

# Web UI baslat
python scripts/ob_test_run.py web

# Sistem saglik kontrolu
python scripts/ob_test_run.py smoke
```

## Web UI

`http://localhost:8081` uzerinde dark theme dashboard.

| Sayfa | URL | Aciklama |
|-------|-----|----------|
| Dashboard | `/` | Aktif testler, son sonuclar, canli log |
| Test Detay | `/test/{key}` | Tek testin tum detaylari |
| Gecmis | `/tests` | Tum testlerin listesi |
| Ayarlar | `/settings` | Ortam ayarlari |
| Smoke Test | `/smoke` | Sistem saglik kontrolu |

### API Endpoint'leri

| Endpoint | Method | Aciklama |
|----------|--------|----------|
| `/api/test/start` | POST | Test pipeline baslat |
| `/api/test/from-jira` | POST | Jira task'tan baslat |
| `/api/test/status/{id}` | GET | Test durumu |
| `/api/tests` | GET | Tum testler |
| `/api/events` | SSE | Canli log akisi |
| `/api/smoke` | GET | Smoke test |

## Ciktilar

Her test `outputs/tests/{TASK_KEY}/` altinda:

```
outputs/tests/PDB-12345/
├── state.json              # Pipeline durumu
├── task-summary.json       # Task ozeti
├── code-analysis.json      # Kod analizi
├── impact-analysis.json    # Etki analizi
├── test-assessment.json    # Test degerlendirmesi
├── test-scenarios.json     # Test senaryolari
├── env-status.json         # Ortam durumu
├── test-results.json       # Test sonuclari
├── verification-report.json # Dogrulama raporu
└── report.md               # Tam rapor
```

## Yapilandirma

### .env

```env
LITELLM_MASTER_KEY=sk-ob-test-local
OB_CORE_PATH=C:\repos\obilet-core-v2
GRAPHIFY_PATH=C:\repos\graphify-out
CONTEXT_PATH=C:\repos\OBTaskManager\obiletcontext
API_PORT=8080
WEB_PORT=8081
LLM_PROFILE=copilot
```

### Pipeline Profilleri

| Profil | Fazlar | Aciklama |
|--------|--------|----------|
| standard | Tum 10 faz | Tam analiz + test |
| quick | ensure_ready → report (5 faz) | Sadece analiz, test yok |

```powershell
$env:PIPELINE_PROFILE="quick"
python scripts/ob_test_run.py launch PDB-12345
```

## Dosya Yapisi

```
ob-test-intelligence/
├── config/
│   ├── app.yaml                  # Uygulama ayarlari
│   ├── litellm/config.yaml       # LLM model tanimlari
│   ├── model_routing.yaml        # Stage → model eslemesi
│   ├── thresholds.yaml           # Risk esik degerleri
│   └── prompts/                  # LLM prompt sablonlari
├── scripts/
│   ├── ob_test_run.py            # CLI runner
│   ├── start_proxy.py            # LiteLLM proxy baslatici
│   └── win/setup.ps1             # Windows kurulum
├── src/app/
│   ├── config.py                 # Ayar yukleme (AppConfig)
│   ├── schemas.py                # Pydantic modeller
│   ├── orchestrator.py           # Pipeline koordinator
│   ├── cli.py                    # Typer CLI
│   ├── integrations/             # Dis bagimliliklar
│   │   ├── litellm_client.py     # LLM proxy client
│   │   ├── graphify_client.py    # Impact analysis
│   │   ├── jira_client.py        # Jira REST API
│   │   ├── git_client.py         # Git diff islemleri
│   │   └── playwright_runner.py  # Web UI test
│   ├── stages/                   # Pipeline fazlari
│   │   ├── ensure_ready.py       # Faz 0
│   │   ├── task_read.py          # Faz 1
│   │   ├── code_analyze.py       # Faz 2
│   │   ├── impact_analyze.py     # Faz 3
│   │   ├── test_assess.py        # Faz 4
│   │   ├── scenario_generate.py  # Faz 5
│   │   ├── env_prepare.py        # Faz 6
│   │   ├── test_execute.py       # Faz 7
│   │   ├── verify.py             # Faz 8
│   │   └── report.py             # Faz 9
│   ├── utils/                    # Yardimci moduller
│   │   ├── logging.py            # Structured logging
│   │   ├── files.py              # Dosya islemleri
│   │   ├── layer_classifier.py   # Katman siniflandirma
│   │   ├── domain_classifier.py  # Domain siniflandirma
│   │   ├── assertion_engine.py   # Assertion motoru
│   │   └── context_loader.py     # obiletcontext yukleyici
│   └── web/
│       ├── app.py                # FastAPI + Web UI
│       └── log_stream.py         # SSE log yayini
├── skills/opencode/
│   ├── SKILL.md                  # opencode skill
│   └── scripts/ob_test_run.py    # Skill wrapper
├── tests/                        # Unit testler (28 test)
└── outputs/tests/                # Calisma ciktilari
```

## Bagimliliklar

### Python

```
fastapi>=0.100.0    uvicorn>=0.20.0    httpx>=0.24.0
pydantic>=2.0.0     structlog>=23.0.0  pyyaml>=6.0
typer>=0.9.0        rich>=13.0.0       python-dotenv>=1.0.0
litellm>=1.40.0     jinja2>=3.1.0      sse-starlette>=1.6.0
```

### Harici

| Bilesen | Konum | Neden |
|---------|-------|-------|
| Graphify | `C:\repos\graphify-out` | Impact analysis |
| obiletcontext | `C:\repos\OBTaskManager\obiletcontext` | Domain knowledge |
| obilet-core-v2 | `C:\repos\obilet-core-v2` | Test edilecek kod |
| Docker Desktop | Local | Test ortami |
| GitHub Copilot lisansi | Sirket | LLM provider (API key gerektirmez) |

## Test

```powershell
# Unit testler
python -m pytest tests/ -v

# Smoke test
python scripts/ob_test_run.py smoke
```

## LLM Provider

GitHub Copilot uzerinden `github_copilot/gpt-4o` kullanilir:

- API key gerektirmez (OAuth device flow)
- Sirket Copilot lisansi yeterli
- Fallback: `github_copilot/gpt-4o-mini`
- LiteLLM proxy (:4000) uzerinden route edilir
