# ob-test-intelligence — Implementation Plan

> oBilet Core V2 icin otomatik test senaryosu uretim, calistirma ve dogrulama araci.
> DQG (doc-quality-gate) mimarisi baz alinarak olusturulur.
> LLM provider: GitHub Copilot (sirket lisansi, API key gerektirmez).

---

## 1. Vizyon & Problem

### Problem

oBilet Core V2 devasa bir kod tabani (215+ entity, 50+ partner, 6 vertical). Bir task implement edildikten sonra:

- Hangi kisimlarin test edilmesi gerektigi belirsiz
- Etki alaninin (blast radius) anlasilmasi zor
- Manuel test senaryosu yazmak zaman alici ve hata yapmaya acik
- Farkli katmanlarin (API, Web, Service) farkli test yontemleri gerektirmesi
- Her developer'in test yaklasiminin farkli olmasi

### Cozum

Bir AI destekli test pipeline'i:

1. Task'tan ne istendigini anlar
2. Yazilan kodun etki alanini tespit eder (Graphify)
3. Test gerekip gerekmedigini belirler
4. Test senaryolarini uretir (obiletcontext ile domain bilgisi)
5. Testleri calistirir (API: HTTP, Web: Playwright MCP)
6. Sonuclari dogrular ve raporlar

### Nasil

DQG'nin basarili mimarisini (Python backend + LiteLLM proxy + FastAPI Web UI + Skill koordinator) birebir uyguluyoruz. Pipeline stage'lerini test-specific logic ile degistiriyoruz. LLM provider olarak `github_copilot/` kullaniyoruz (API key gerektirmez, herkesin Copilot lisansi yeterli).

---

## 2. Mimari

### 2.1 Genel Mimari (DQG Modeli)

```
Kullanici (opencode / Copilot / CLI)
    |
    v
Skill (SKILL.md)              <-- opencode skill, ince koordinator
    | subprocess cagrisi
    v
ob_test_run.py (CLI)          <-- launch, poll, report, execute
    | HTTP API
    v
FastAPI Web Server (:8081)    <-- Pipeline API + Web UI + SSE
    |
    +-- Background Thread     <-- Pipeline orchestrator
    |       |
    |       +-- LiteLLM Proxy (:4000)  <-- github_copilot/gpt-4o
    |
    +-- Graphify              <-- Impact analysis (node subprocess)
    +-- Playwright            <-- Web UI test (subprocess)
    +-- obiletcontext/        <-- Domain knowledge (file reads)
```

### 2.2 Neden DQG Modeli

| Neden | Aciklama |
|-------|----------|
| Kanitlanmis mimari | DQG aylardir calisiyor, production-ready |
| Web UI hazır | FastAPI + inline HTML, ek frontend dependency yok |
| LiteLLM entegrasyonu | Model routing, fallback, retry hazır |
| Background processing | Uzun suren islemler thread'de, polling ile takip |
| SSE canli log | Tarayicidan anlik takip |
| CLI + Skill | Hem AI assistant hem standalone kullanim |
| Self-healing | DQG'nin auto-fix pattern'leri |

### 2.3 Neden GitHub Copilot

| Neden | Aciklama |
|-------|----------|
| Sirkette herkeste var | Ek lisans gerekmez |
| API key gerektirmez | OAuth device flow, bir kere auth |
| Maliyet yok | Copilot lisansina dahil |
| Guclu modeller | gpt-4o, gpt-4o-mini, gpt-4 |
| LiteLLM destegi | `github_copilot/` prefix ile direkt calisir |

---

## 3. Pipeline

```
TASK_READ → CODE_ANALYZE → IMPACT_ANALYZE → TEST_NEED_ASSESS → [USER] →
SCENARIO_GENERATE → [USER] → ENV_PREPARE → TEST_EXECUTE → VERIFY → REPORT
```

Her `[USER]` = AI durur, ozet sunar, onay bekler.

### 3.1 Pipeline State File

**Konum:** `outputs/tests/{TASK_KEY}/state.json`

```json
{
  "task_key": "PDB-12345",
  "task_source": "jira",
  "current_phase": "CODE_ANALYZE",
  "phases_completed": ["TASK_READ"],
  "project_path": "C:\\repos\\obilet-core-v2",
  "config": {
    "graphify_path": "C:\\repos\\graphify-out",
    "context_path": "C:\\repos\\OBTaskManager\\obiletcontext",
    "ob_core_path": "C:\\repos\\obilet-core-v2",
    "api_port": 8080,
    "web_port": 8081,
    "llm_profile": "copilot"
  },
  "artifacts": {
    "task_summary": "",
    "code_analysis": "",
    "impact_analysis": "",
    "test_assessment": "",
    "test_scenarios": "",
    "test_results": "",
    "verification_report": ""
  },
  "created_at": "",
  "updated_at": ""
}
```

### 3.2 Fazlar

---

#### FAZ 0: ENSURE_READY

**Ne:** Altyapiyi kontrol et, eksikse kur.

**Neden:** Her kullanicinin ortami farkli. Auto-setup olmadan calismaz.

**Nasil:**
1. `.venv` var mi → yoksa `python -m venv .venv` + `pip install -r requirements.txt`
2. LiteLLM proxy calisiyor mu (`:4000/health`) → yoksa baslat
3. Copilot OAuth token var mi (`~/.config/litellm/github_copilot/`) → yoksa device flow baslat
4. Graphify graph.json var mi (`C:\repos\graphify-out\graph.json`) → yoksa uyar
5. obiletcontext erisilebilir mi (`C:\repos\OBTaskManager\obiletcontext\prd.md`) → yoksa uyar
6. FastAPI web server calisiyor mu (`:8081/api/status`) → yoksa baslat

**Self-healing (DQG'den gelen pattern):**
- pip install basarisiz → `--no-cache` tekrar dene
- Proxy baslamadi → portu oldur, tekrar baslat
- Copilot auth basarisiz → tekrar device flow baslat
- Port 4000/8081 dolu → prosesi oldur

---

#### FAZ 1: TASK_READ

**Ne:** Jira'dan task'i oku, ne istendigini anla.

**Neden:** Test senaryolarini dogru uretmek icin once "ne yapildi" ve "ne bekleniyor" bilmek gerekir.

**Nasil:**
1. `jira_jira_get_issue(issue_key="{INPUT}", fields="description,reporter,assignee,priority,status,summary,issuetype")`
2. `jira_jira_get_issue(issue_key="{INPUT}", fields="comment", comment_limit=20)` — yorumlari oku
3. Branch/PR bilgisini al → `jira_jira_get_issue_development_info(issue_key="{INPUT}")`
4. obiletcontext'ten ilgili domain dokumanini yukle:
   - Task summary'de "bus" geciyorsa → `obiletcontext/domain/bus.md`
   - "flight" geciyorsa → `obiletcontext/domain/flight.md`
   - "hotel" → `hotel.md`, "sea" → `sea.md`, vb.
5. Her zaman yukle: `prd.md` (is kurallari), `glossary.md` (terminoloji)

**LLM kullanimi:** Task summary + description + comments → LLM ile ozetle, test-relevant noktalari cikar.

**Cikti:** `outputs/tests/{TASK_KEY}/task-summary.json`

```json
{
  "task_key": "PDB-12345",
  "title": "...",
  "description_summary": "...",
  "domain": "bus",
  "affected_verticals": ["bus"],
  "what_changed": "Bus arama sonuclarina branded fare filtresi eklendi",
  "expected_behavior": "Kullanici branded fare tipine gore filtreleyebilmeli",
  "acceptance_criteria": ["..."],
  "branch": "feature/PDB-12345-branded-fare-filter",
  "risk_level": "medium",
  "relevant_context_files": ["domain/bus.md", "prd.md"]
}
```

---

#### FAZ 2: CODE_ANALYZE

**Ne:** Branch diff'ten degisen dosyalari tespit et, katman ve domain analizi yap.

**Neden:** Neyin test edilecegini bilmek icin once neyin degistigini anlamaliyiz. Katman bilgisi test yontemini belirler.

**Nasil:**
1. Branch'i belirle (Jira dev info veya sor):
   ```powershell
   git -C "C:\repos\obilet-core-v2" diff main...{branch} --name-only
   ```
2. Her dosyayi siniflandir:
   ```
   src/api/Controllers/*.cs      → layer: "api_controller"
   src/web/Controllers/*.cs      → layer: "web_controller"
   src/services/**/*.cs          → layer: "service"
   src/core/**/*.cs              → layer: "core_model"
   src/services/Data/Entities/*  → layer: "entity"
   src/services/*/Providers/*    → layer: "provider"
   ```
3. Domain tespit et (namespace/class adindan):
   ```
   BusService, BusJourney → domain: "bus"
   FlightBooking → domain: "flight"
   HotelService → domain: "hotel"
   PaymentService → domain: "payment"
   ```
4. Degisiklik turunu tespit et:
   ```
   Yeni endpoint eklendi    → change_type: "new_api"
   Mevcut endpoint degisti  → change_type: "api_change"
   Service logic degisti    → change_type: "service_logic"
   DTO/model degisti        → change_type: "model_change"
   UI degisti               → change_type: "ui_change"
   ```

**LLM kullanimi:** Diff + dosya icerikleri → LLM ile "bu degisiklik ne yapiyor, hangi katman, hangi domain, ne tur bir degisiklik" analizi.

**Cikti:** `outputs/tests/{TASK_KEY}/code-analysis.json`

```json
{
  "branch": "feature/PDB-12345",
  "files_changed": [
    {
      "path": "src/api/Controllers/JourneyController.cs",
      "layer": "api_controller",
      "domain": "bus",
      "change_type": "api_change",
      "summary": "GetJourneys endpoint'ine brandedFareFilter parametresi eklendi"
    },
    {
      "path": "src/services/Bus/BusService.cs",
      "layer": "service",
      "domain": "bus",
      "change_type": "service_logic",
      "summary": "GetJourneys metodunda filtreleme logic'i eklendi"
    }
  ],
  "layers_affected": ["api_controller", "service"],
  "domains_affected": ["bus"],
  "endpoints_affected": [
    {"method": "POST", "path": "/api/journey/getjourneys", "controller": "JourneyController"}
  ]
}
```

---

#### FAZ 3: IMPACT_ANALYZE

**Ne:** Graphify ile degisen dosyalarin etki alanini analiz et.

**Neden:** Bir dosya degistiginde baska nelerin etkilendigini bilmek, test kapsamini belirler. Ornegin BusService degistiginde JourneyController, PaymentService vb. de etkilenebilir.

**Nasil:**
1. CODE_ANALYZE'den dosya listesini al
2. Graphify'i calistir:
   ```powershell
   node "C:\repos\graphify-out\impact-query.js" "{comma-separated files}" --depth 2
   ```
   **Timeout: 120000** (76MB graph.json yuklemesi 3-5 saniye surer)
3. Sonucu parse et:
   - 1-hop (dogrudan etkilenen): bu dosyalari calisan testler var mi?
   - 2-hop (dolayli etkilenen): regresyon riski
   - Community'ler: hangi moduller tehlikede?
   - God nodes: merkezi bileşenler etkilendiyse yuksek risk
4. Risk seviyesi hesapla:
   ```
   Yuksek: Payment,Financial,Security katmani etkilendiyse
   Orta:   Search,Listing,State degisiklikleri
   Dusuk:  UI cosmetic, documentation
   ```

**LLM kullanimi:** Graphify sonuclari + code analysis → LLM ile "bu etki alanindaki dosyalar hangi islevleri yerine getiriyor, regresyon riski nedir" analizi.

**Cikti:** `outputs/tests/{TASK_KEY}/impact-analysis.json`

```json
{
  "seed_files": ["src/api/Controllers/JourneyController.cs", "..."],
  "one_hop": {
    "count": 12,
    "files": [
      {"path": "...", "type": "controller", "risk": "medium"},
      ...
    ]
  },
  "two_hop": {
    "count": 34,
    "highlights": ["..."]
  },
  "communities_affected": [
    {"name": "bus-search", "node_count": 15},
    {"name": "journey-listing", "node_count": 8}
  ],
  "god_nodes_affected": [],
  "overall_risk": "medium",
  "regression_areas": ["bus journey listing", "partner integration"]
}
```

---

#### FAZ 4: TEST_NEED_ASSESS

**Ne:** Etkilenen alanlarin test edilip edilmeyecegine karar ver. Test edilecekse hangi yontemle.

**Neden:** Her degisiklik test gerektirmez. CSS degisikligi icin API test yazmak zaman kaybi. Ama Payment service degisikligi icin test sart. Yanlis test yontemi secmek de zaman kaybi.

**Nasil:** Karar agaci uygula:

**Adim 1: Test gerekiyor mu?**

```
change_type == "ui_change" AND layer == "web" AND sadece CSS/HTML → SKIP
change_type == "model_change" AND sadece yeni field → minimal test
change_type == "api_change" → ZORUNLU test
change_type == "service_logic" → ZORUNLU test
change_type == "new_api" → ZORUNLU test
domain == "payment" → HER ZAMAN test
risk == "high" → HER ZAMAN test
```

**Adim 2: Test turu ne?**

```
layer == "api_controller" → API test
layer == "web_controller" → Web UI test (Playwright)
layer == "service" → Bu service'i cagiran controller'i bul:
    controller == api_controller → API test
    controller == web_controller → Web UI test
layer == "provider" → Mock integration test (karmasik, MANUAL flag)
layer == "entity" → DB migration test
layer == "core_model" → Serialization test
```

**Adim 3: Test ortami**

```
test_type == "api" → Docker ile API ayaklandir (docker-compose.local.yml)
test_type == "web" → Docker ile Web ayaklandir, API uzak sunucudan (stage)
```

**Adim 4: Test onceligi**

```
domain == "payment" → p0 (en yuksek)
domain == "bus" AND islem == "purchase" → p0
domain == "bus" AND islem == "search" → p1
domain == "hotel" → p1
tum digerleri → p2
```

**LLM kullanimi:** Code analysis + impact analysis + domain knowledge → LLM ile "bu dosyalar icin test gerekiyor mu, gerekiyorsa hangi tur, neden" kararini uret.

**Cikti:** `outputs/tests/{TASK_KEY}/test-assessment.json`

```json
{
  "needs_testing": true,
  "test_items": [
    {
      "id": "T1",
      "target": "JourneyController.GetJourneys",
      "test_type": "api",
      "priority": "p1",
      "reason": "API endpoint'ine yeni parametre eklendi, response yapisi degismis olabilir",
      "layer": "api_controller",
      "domain": "bus",
      "risk": "medium"
    },
    {
      "id": "T2",
      "target": "BusService.GetJourneys",
      "test_type": "api",
      "priority": "p1",
      "reason": "Service logic degisti, filtreleme eklendi",
      "layer": "service",
      "domain": "bus",
      "risk": "medium"
    }
  ],
  "skip_items": [
    {
      "target": "BusJourney.cs",
      "reason": "Sadece yeni property eklendi, serialization test yeterli",
      "suggested_action": "manual_check"
    }
  ],
  "environment": {
    "type": "api",
    "requires_docker": true,
    "docker_compose": "docker-compose.local.yml",
    "api_url": "http://localhost:8080"
  }
}
```

**Kullaniciya sunum:**
```
TEST DEGERLENDIRMESI

Test gerekiyor: EVET
Test adedi: 2 API, 0 Web
Ortam: Docker API (local)

Test maddeleri:
  T1 [P1] JourneyController.GetJourneys — API test
       Neden: Yeni parametre eklendi
  T2 [P1] BusService.GetJourneys — API test
       Neden: Filtreleme logic degisti

Atlanan:
  BusJourney.cs — sadece yeni property

Yanitla: "Onayliyorum" → senaryo uretimine gecerim
         "T1'i atla" → o maddeleri cikaririm
         "Hepsini test et" → skip maddeleri de eklerim
```

**WAIT for user response.**

---

#### FAZ 5: SCENARIO_GENERATE

**Ne:** Her test maddesi icin detayli test senaryolari uret.

**Neden:** Dogru test senaryosu uretmek icin is kurallarini (obiletcontext), kodun nasil calistigini (code analysis) ve beklenen ciktiyi (task requirements) birlestirmek gerekir. Bu safhanin "zekasi" burada.

**Nasil:**

**Adim 1: Context hazirla**
Her test maddesi icin ilgili context'i yukle:
- `obiletcontext/domain/{domain}.md` → Domain is kurallari
- `obiletcontext/infrastructure/api-pipeline.md` → API nasil calisir
- `obiletcontext/architecture.md` → Response pattern, error handling
- `obiletcontext/conventions.md` → Kod yapisi

**Adim 2: Senaryo sablonu**
Her senaryo su yapida olmali:

```json
{
  "id": "T1-S1",
  "test_item_id": "T1",
  "name": "Normal arama branded fares ile",
  "type": "happy_path",
  "steps": [
    {
      "action": "http_request",
      "method": "POST",
      "url": "/api/journey/getjourneys",
      "headers": {"Authorization": "Basic {creds}"},
      "body": {
        "departureId": 34,
        "arrivalId": 16,
        "date": "2026-06-15"
      }
    }
  ],
  "assertions": [
    {"field": "status", "operator": "equals", "value": "Success"},
    {"field": "data.journeys", "operator": "is_not_empty"},
    {"field": "data.journeys[0].brandedFares", "operator": "is_not_null"}
  ],
  "expected_status_code": 200
}
```

**Adim 3: Senaryo tipleri (her test maddesi icin)**
- **Happy path:** Normal akis, dogru parametreler → basarili response
- **Edge case:** Sinir degerleri (bos liste, tek sonuc, cok fazla sonuc)
- **Error case:** Gecersiz parametre → hatagli response
- **Regression:** Impact analysis'ten etkilenen alanlarin hala calistigini dogrula

**Adim 4: Domain-specific senaryo kurallari**

| Domain | Zorunlu Senaryolar |
|--------|--------------------|
| Bus | Arama → CheckVacancy → Purchase akisi, iptal |
| Flight | Search → Allocate → PrePurchase → Purchase |
| Hotel | Search → GetOffers → BeginTransaction → Commit |
| Payment | Odeme akisi, refund, kupon uygulamasi |
| Sea | Search → Allocate → Purchase |
| RentACar | Search → PreReservation → Finalization |

**LLM kullanimi:** Code analysis + domain context + task requirements → LLM ile "bu endpoint'e bu parametreleri gonderirsem bu response'u beklerim" senaryolarini uret. obiletcontext'ten is kurallarini okuyarak dogru assertion'lari olustur.

**Cikti:** `outputs/tests/{TASK_KEY}/test-scenarios.json`

**Kullaniciya sunum:**
```
TEST SENARYOLARI

Toplam: 6 senaryo (2 happy, 2 edge, 1 error, 1 regression)

T1-S1: Normal arama branded fares ile [happy]
T1-S2: Filtre parametresi ile arama [happy]
T1-S3: Bos tarih araligi [edge]
T1-S4: Gecmis tarihli arama [error]
T1-S5: BrandedFare null response [edge]
T2-S1: Service filtreleme regression [regression]

Tam liste: outputs/tests/{TASK_KEY}/test-scenarios.json

Yanitla: "Onayliyorum" → test calistirmaya gecerim
         "T1-S3'u kaldir" → senaryoyu cikaririm
         "Bir senaryo daha ekle: ..." → eklerim
```

**WAIT for user response.**

---

#### FAZ 6: ENV_PREPARE

**Ne:** Test ortamini ayaklandir.

**Neden:** API veya Web testi calistirmak icin uygulamanin calismasi gerekir. Local docker ortami veya remote stage ortami kullanilabilir.

**Nasil:**

**API Test icin:**
```powershell
# docker-compose.local.yml ile local ortam
cd C:\repos\obilet-core-v2\src
docker-compose -f docker-compose.local.yml up -d api

# Health check
$url = "http://localhost:8080/health"
$maxAttempts = 30
for ($i = 0; $i -lt $maxAttempts; $i++) {
    try {
        $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { break }
    } catch {}
    Start-Sleep -Seconds 2
}
```

**Web Test icin:**
```powershell
# Web app + remote API (stage)
# appsettings.json'da API URL'i stage'e yonlendir
cd C:\repos\obilet-core-v2\src
docker-compose -f docker-compose.local.yml up -d web

# Playwright hazirlik (zorunlu degil, MCP varsa kullanilir)
# Playwright MCP zaten mevcut, ek kurulum gerekmez
```

**Ortam durumu kontrolu:**
```json
{
  "environment": "local_docker",
  "api_url": "http://localhost:8080",
  "api_healthy": true,
  "web_url": "http://localhost:8081",
  "web_healthy": false,
  "auth_configured": true,
  "test_credentials": {"consumer_key": "...", "device_id": "..."}
}
```

---

#### FAZ 7: TEST_EXECUTE

**Ne:** Test senaryolarini calistir.

**Neden:** Pipeline'in kalbi. Uretilen senaryolarin gercekten calisip calismadigini gormek.

**Nasil:**

**API Test (PowerShell/HTTP):**

Her senaryo icin:
1. HTTP request olustur (method, url, headers, body)
2. Request'i gonder (`Invoke-WebRequest` veya `Invoke-RestMethod`)
3. Response'u kaydet (status code, body, headers)
4. Assertion'lari kontrol et

```python
# Python executor (FastAPI background thread)
import httpx

async def execute_api_test(scenario):
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=scenario["method"],
            url=f"{base_url}{scenario["url"]}",
            headers=scenario["headers"],
            json=scenario["body"],
            timeout=30.0
        )
    
    results = []
    for assertion in scenario["assertions"]:
        result = check_assertion(response, assertion)
        results.append(result)
    
    return {
        "scenario_id": scenario["id"],
        "status_code": response.status_code,
        "response_body": response.json(),
        "assertion_results": results,
        "passed": all(r["passed"] for r in results),
        "duration_ms": ...
    }
```

**Web UI Test (Playwright MCP):**

Skill uzerinden (opencode kullaniyorsa):
```
1. Playwright browser_navigate → sayfayi ac
2. Playwright browser_snapshot → sayfa durumunu al
3. Playwright browser_click/type → form doldur, butona tikla
4. Playwright browser_snapshot → sonucu kontrol et
5. Assertion'lari sayfa icerigi ile karsilastir
```

CLI uzerinden (standalone):
```python
# Playwright subprocess
import subprocess

def execute_web_test(scenario):
    result = subprocess.run(
        ["python", "-m", "playwright", "test", scenario["script_path"]],
        capture_output=True, text=True, timeout=60
    )
    return parse_playwright_output(result.stdout)
```

**Cikti:** `outputs/tests/{TASK_KEY}/test-results.json`

```json
{
  "execution_time": "2026-06-10T14:30:00Z",
  "total_scenarios": 6,
  "passed": 5,
  "failed": 1,
  "skipped": 0,
  "results": [
    {
      "scenario_id": "T1-S1",
      "name": "Normal arama branded fares ile",
      "passed": true,
      "status_code": 200,
      "assertions": [
        {"field": "status", "expected": "Success", "actual": "Success", "passed": true},
        {"field": "data.journeys", "expected": "not_empty", "actual": "[15 items]", "passed": true},
        {"field": "data.journeys[0].brandedFares", "expected": "not_null", "actual": "[3 items]", "passed": true}
      ],
      "duration_ms": 342
    },
    {
      "scenario_id": "T1-S4",
      "name": "Gecmis tarihli arama",
      "passed": false,
      "status_code": 400,
      "assertions": [
        {"field": "status", "expected": "InvalidRequestData", "actual": "InvalidRequestData", "passed": true},
        {"field": "userMessage", "expected": "not_null", "actual": "null", "passed": false, "reason": "UserMessage null geldi, localization calismiyor olabilir"}
      ],
      "duration_ms": 45
    }
  ]
}
```

---

#### FAZ 8: VERIFY

**Ne:** Test sonuclarini derinlemesine analiz et. Gecenleri dogrula, kalabalari nedenleriyle raporla.

**Neden:** Test gecti ama gercekten dogru mu? Assertion'lar yuzeysel kalmis olabilir. Test kaldi ama bug mi yoksa test senaryosu mu yanlis? Bu faz derinlemesine analiz yapar.

**Nasil:**

1. **False positive kontrolu:** Gecen testlerde response'un beklenen is kurallarina uygun olup olmadigini kontrol et
2. **False negative analizi:** Kalan testlerde neden kaldi:
   - Bug (kod hatasi) → raporla
   - Test senaryosu hatasi → senaryoyu duzelt, tekrar calistir
   - Ortam sorunu → ortami duzelt, tekrar calistir
   - Data sorunu → farkli data ile tekrar dene
3. **Regression analizi:** Impact analysis'teki dosyalar icin ek sorunlar var mi
4. **Coverage raporu:** Test edilen alanlar vs etki alanlari karsilastirmasi

**LLM kullanimi:** Test results + expected behavior (task + domain context) → LLM ile "bu sonuclar beklenenle uyusuyor mu, nerede sapma var, neden" analizi.

**Cikti:** `outputs/tests/{TASK_KEY}/verification-report.json`

```json
{
  "overall_verdict": "PASS_WITH_NOTES",
  "coverage_percentage": 85,
  "test_quality": "good",
  "findings": [
    {
      "severity": "medium",
      "type": "potential_bug",
      "description": "Gecmis tarihli aramada UserMessage null donuyor. Localization calismiyor olabilir.",
      "affected_scenario": "T1-S4",
      "recommendation": "LocalizeResultFilter'in bu endpoint icin calistigini kontrol et"
    },
    {
      "severity": "info",
      "type": "coverage_gap",
      "description": "BrandedFares'in null geldigi senaryo test edilmedi",
      "recommendation": "Partner branded fare desteklemiyorsa bile response duzgun olmali"
    }
  ],
  "false_positives": [],
  "false_negatives": [
    {
      "scenario": "T1-S4",
      "reason": "test_scenario_error",
      "detail": "Assertion userMessage beklentisi localization katmanina bagimli, API test icin uygun degil"
    }
  ]
}
```

---

#### FAZ 9: REPORT

**Ne:** Tam rapor olustur, Web UI'da goster, dosyaya kaydet.

**Nasil:**

1. Tum artifact'lari birlestir → final rapor
2. Web UI'da goster (`http://localhost:8081/test/{test_id}`)
3. Skill'e ozet don (CLI/stdout)
4. Dosyaya kaydet (`outputs/tests/{TASK_KEY}/report.md`)

**Rapor formati:**
```markdown
# Test Report: PDB-12345

## Ozet
- Task: Bus aramada branded fare filtresi
- Sonuc: PASS WITH NOTES
- Coverage: 85%
- Gecen: 5/6 senaryo

## Test Senaryolari
| ID | Ad | Tur | Sonuc | Sure |
|----|-----|------|-------|------|
| T1-S1 | Normal arama | happy | PASS | 342ms |
| T1-S4 | Gecmis tarih | error | FAIL | 45ms |

## Bulgular
- [MEDIUM] UserMessage null - localization sorunu
- [INFO] Coverage gap - brandedFares null senaryosu

## Ortam
- API: http://localhost:8080 (Docker)
- Calisma suresi: 45 saniye
```

---

## 4. Dosya Yapisi

```
ob-test-intelligence/
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
│
├── config/
│   ├── app.yaml                      # Uygulama ayarlari
│   ├── litellm/
│   │   └── config.yaml               # github_copilot/ model tanimlari
│   ├── model_routing.yaml            # Stage → model grup eslemesi
│   ├── pipeline_profiles.yaml        # Hizli/derin pipeline profilleri
│   ├── prompts/                      # LLM prompt sablonlari
│   │   ├── task_analyzer.md          # Faz 1: Task analiz prompt
│   │   ├── code_analyzer.md          # Faz 2: Kod analiz prompt
│   │   ├── impact_assessor.md        # Faz 3: Etki degerlendirme prompt
│   │   ├── test_assessor.md          # Faz 4: Test ihtiyac degerlendirme prompt
│   │   ├── scenario_generator.md     # Faz 5: Senaryo uretim prompt
│   │   └── result_verifier.md        # Faz 8: Sonuc dogrulama prompt
│   └── thresholds.yaml               # Risk esik degerleri
│
├── scripts/
│   ├── ob_test_run.py                # CLI runner (dqg_run.py muadili)
│   ├── start_proxy.py                # LiteLLM proxy baslatici
│   ├── win/                          # Windows helper scriptleri
│   │   └── setup.ps1
│   ├── linux/                        # Linux helper scriptleri
│   └── mac/                          # Mac helper scriptleri
│
├── src/
│   └── app/
│       ├── __init__.py
│       ├── config.py                 # Ayar yukleme (AppConfig)
│       ├── schemas.py                # Pydantic modeller
│       ├── orchestrator.py           # Pipeline koordinator
│       ├── cli.py                    # Typer CLI (python -m app.cli test PDB-XXX)
│       ├── integrations/
│       │   ├── litellm_client.py     # LiteLLM proxy client
│       │   ├── graphify_client.py    # Graphify impact-query.js wrapper
│       │   ├── jira_client.py        # Jira REST API client
│       │   ├── git_client.py         # Git diff, branch islemleri
│       │   └── playwright_runner.py  # Playwright test executor
│       ├── stages/
│       │   ├── ensure_ready.py       # Faz 0: Altyapi kontrol
│       │   ├── task_read.py          # Faz 1: Jira okuma
│       │   ├── code_analyze.py       # Faz 2: Kod analizi
│       │   ├── impact_analyze.py     # Faz 3: Graphify etki analizi
│       │   ├── test_assess.py        # Faz 4: Test ihtiyac degerlendirme
│       │   ├── scenario_generate.py  # Faz 5: Senaryo uretimi
│       │   ├── env_prepare.py        # Faz 6: Ortam hazirlama
│       │   ├── test_execute.py       # Faz 7: Test calistirma
│       │   ├── verify.py             # Faz 8: Sonuc dogrulama
│       │   └── report.py             # Faz 9: Raporlama
│       ├── utils/
│       │   ├── logging.py            # Structured logging
│       │   ├── files.py              # Dosya islemleri
│       │   ├── layer_classifier.py   # Dosya → katman siniflandirma
│       │   ├── domain_classifier.py  # Dosya → domain siniflandirma
│       │   ├── assertion_engine.py   # Assertion kontrol motoru
│       │   └── context_loader.py     # obiletcontext yukleyici
│       └── web/
│           ├── __init__.py
│           ├── app.py                # FastAPI uygulama (Web UI + API)
│           └── log_stream.py         # SSE log yayini
│
├── outputs/                          # Calisma zamaninda olusur
│   └── tests/
│       └── {TASK_KEY}/
│           ├── state.json
│           ├── task-summary.json
│           ├── code-analysis.json
│           ├── impact-analysis.json
│           ├── test-assessment.json
│           ├── test-scenarios.json
│           ├── test-results.json
│           ├── verification-report.json
│           └── report.md
│
├── skills/
│   └── opencode/
│       ├── SKILL.md                  # opencode skill tanimi
│       └── scripts/
│           └── ob_test_run.py        # Skill wrapper (DQG pattern)
│
└── tests/                            # Unit testler
    ├── test_layer_classifier.py
    ├── test_domain_classifier.py
    ├── test_assertion_engine.py
    └── test_orchestrator.py
```

---

## 5. LiteLLM Konfigurasyonu

### config/litellm/config.yaml

```yaml
model_list:
  - model_name: analyzer
    litellm_params:
      model: github_copilot/gpt-4o
  - model_name: scenario_gen
    litellm_params:
      model: github_copilot/gpt-4o
  - model_name: verifier
    litellm_params:
      model: github_copilot/gpt-4o
  - model_name: fallback
    litellm_params:
      model: github_copilot/gpt-4o-mini

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  timeout: 300
  allowed_fails: 3
  fallbacks:
    - analyzer: [fallback]
    - scenario_gen: [fallback]
    - verifier: [fallback]

litellm_settings:
  drop_params: true
  num_retries: 2
  request_timeout: 300

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

### config/model_routing.yaml

```yaml
model_groups:
  analyzer:
    provider: github_copilot
    model: github_copilot/gpt-4o
    description: Kod ve etki analizi icin
  scenario_gen:
    provider: github_copilot
    model: github_copilot/gpt-4o
    description: Test senaryosu uretimi icin
  verifier:
    provider: github_copilot
    model: github_copilot/gpt-4o
    description: Sonuc dogrulama icin
  fallback:
    provider: github_copilot
    model: github_copilot/gpt-4o-mini
    description: Hizli fallback model

routing:
  task_analyze: analyzer
  code_analyze: analyzer
  impact_assess: analyzer
  test_assess: analyzer
  scenario_generate: scenario_gen
  verify: verifier
```

---

## 6. Web UI

### Sayfalar

| Sayfa | URL | Aciklama |
|-------|-----|----------|
| Dashboard | `/` | Aktif test, son sonuclar, sistem durumu |
| Test Detail | `/test/{id}` | Tek testin tum detaylari |
| Gecmis | `/tests` | Tum testlerin listesi |
| Settings | `/settings` | Model routing, ortam ayarlari |
| Smoke Test | `/smoke` | Sistem saglik kontrolu |

### API Endpoint'leri

| Endpoint | Method | Aciklama |
|----------|--------|----------|
| `/api/test/start` | POST | Test pipeline baslat (async) |
| `/api/test/status/{id}` | GET | Test durumu sorgula |
| `/api/test/from-jira` | POST | Jira task'tan test baslat |
| `/api/tests` | GET | Tum testlerin listesi |
| `/api/tests/{id}` | GET | Tek test detayi |
| `/api/events` | GET (SSE) | Canli log akisi |
| `/api/status` | GET | Sistem durumu (proxy, docker) |
| `/api/models` | GET | Model gruplari |
| `/api/models/routing` | POST | Model routing guncelle |
| `/api/smoke` | GET | Smoke test |

### Web UI Teknoloji

DQG ile ayni yaklasim: **Inline HTML** (ayri frontend build yok).

- FastAPI `HTMLResponse` ile her sayfa kendi HTML'ini render eder
- CSS: Custom dark theme (DQG ile tutarli)
- JS: Vanilla JavaScript, fetch API
- SSE: EventSource ile canli log

---

## 7. Skill Entegrasyonu

### SKILL.md (opencode icin)

```yaml
---
name: ob-test-intelligence
description: "oBilet test intelligence pipeline. Task-based test scenario generation,
  execution and verification. Uses Graphify for impact analysis, GitHub Copilot for LLM,
  obiletcontext for domain knowledge."
---
```

### Skill Akisi

```
Kullanici: "test PDB-12345"
    |
    v
Skill: ob_test_run.py launch PDB-12345
    → LiteLLM proxy baslat (gerekirse)
    → Web server baslat (gerekirse)
    → Tarayici ac (http://localhost:8081)
    → REVIEW_STARTED test_id=xxx
    |
    v
Skill: ob_test_run.py poll xxx
    → STATUS: running...
    → STATUS: running...
    → TEST_COMPLETE
    → Sonuclari goster
    |
    v
Skill: Kullaniciya ozet sun, onay bekle
```

### Skill'in Yaptigi (ince koordinator)

1. `ob_test_run.py` subprocess cagrisi (launch, poll)
2. Sonuclari oku ve kullaniciya sun
3. Kullanici onayini bekle
4. Gerekirse Playwright MCP ile Web UI test calistir (sadece opencode'da)

### Skill'in Yapmadigi (Python backend yapar)

- LLM cagrilari
- Graphify cagrilari
- Docker yonetimi
- HTTP test execution
- State management
- Web UI

---

## 8. obiletcontext Entegrasyonu

### Yukleme Stratejisi

| Faz | Yuklenen Dosyalar | Neden |
|-----|-------------------|-------|
| TASK_READ | `prd.md`, `glossary.md`, `domain/{domain}.md` | Is kurallari ve terminoloji |
| CODE_ANALYZE | `architecture.md`, `conventions.md` | Kod yapisi ve pattern'ler |
| IMPACT_ANALYZE | `domain/{affected}.md` | Domain-specific kurallar |
| TEST_NEED_ASSESS | Hepsi birlesik | Karar vermek icin |
| SCENARIO_GENERATE | `domain/{domain}.md`, `infrastructure/api-pipeline.md`, `guides/new-controller.md` | Test senaryosu uretimi |
| TEST_EXECUTE | `infrastructure/api-pipeline.md` | Auth, request format |
| VERIFY | `prd.md`, `architecture.md` | Beklenen davranis |

### Context Loader

```python
class ContextLoader:
    def __init__(self, context_path: str):
        self.context_path = Path(context_path)
    
    def load_for_phase(self, phase: str, domain: str = "") -> str:
        docs = []
        
        # Her faz icin ortak
        if phase in ("task_read", "test_assess", "verify"):
            docs.append(self._read("prd.md"))
            docs.append(self._read("glossary.md"))
        
        # Faz-specific
        if phase == "code_analyze":
            docs.append(self._read("architecture.md"))
            docs.append(self._read("conventions.md"))
        
        if phase in ("scenario_generate", "test_execute"):
            if domain:
                docs.append(self._read(f"domain/{domain}.md"))
            docs.append(self._read("infrastructure/api-pipeline.md"))
        
        if domain and phase in ("task_read", "impact_assess"):
            docs.append(self._read(f"domain/{domain}.md"))
        
        return "\n\n---\n\n".join(docs)
    
    def _read(self, relative_path: str) -> str:
        path = self.context_path / relative_path
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
```

---

## 9. Implementasyon Takvimi

### Faz A: Cekirdek Altyapi (3-4 gun)

**Hedef:** DQG iskeletini kopyala, test-specific hale getir.

| Adim | Ne | Neden | Sure |
|------|-----|-------|------|
| A1 | DQG'den dosya yapısını kopyala | Sifirdan yazmaya gerek yok | 0.5g |
| A2 | `config/litellm/config.yaml` → github_copilot/ yapilandir | API key'siz LLM | 0.5g |
| A3 | `src/app/config.py` → test-specific ayarlar | Test pipeline konfigürasyonu | 0.5g |
| A4 | `src/app/orchestrator.py` → test pipeline stage'leri | 9 faz pipeline'i | 1g |
| A5 | `src/app/web/app.py` → test dashboard HTML | Web UI | 1g |
| A6 | `scripts/ob_test_run.py` → CLI runner | Skill + standalone kullanim | 0.5g |

### Faz B: Analiz ve Zeka (3-4 gun)

**Hedef:** Faz 1-5 pipeline logic'i.

| Adim | Ne | Neden | Sure |
|------|-----|-------|------|
| B1 | `task_read.py` → Jira okuma + domain tespit | Task anlama | 0.5g |
| B2 | `code_analyze.py` → Git diff + katman/domain siniflandirma | Kod anlama | 1g |
| B3 | `impact_analyze.py` → Graphify wrapper | Etki alani tespiti | 0.5g |
| B4 | `test_assess.py` → Karar agaci + LLM degerlendirme | Test ihtiyac karari | 1g |
| B5 | `scenario_generate.py` → LLM senaryo uretimi + obiletcontext | Test senaryoları | 1g |
| B6 | `context_loader.py` → obiletcontext yukleyici | Domain bilgisi | 0.5g |

### Faz C: Execution ve Dogrulama (3-4 gun)

**Hedef:** Faz 6-9 pipeline logic'i.

| Adim | Ne | Neden | Sure |
|------|-----|-------|------|
| C1 | `env_prepare.py` → Docker ortam yonetimi | Test ortami | 1g |
| C2 | `test_execute.py` → HTTP test executor | API test calistirma | 1g |
| C3 | `assertion_engine.py` → Assertion kontrol motoru | Sonuc dogrulama | 0.5g |
| C4 | `verify.py` → False positive/negative analizi | Derinlemesine analiz | 1g |
| C5 | `report.py` → Rapor olusturma | Sonuc raporlama | 0.5g |

### Faz D: Skill ve Polisaj (2-3 gun)

**Hedef:** opencode skill, test, dokumantasyon.

| Adim | Ne | Neden | Sure |
|------|-----|-------|------|
| D1 | `skills/opencode/SKILL.md` → Skill tanimi | opencode entegrasyonu | 0.5g |
| D2 | Playwright MCP entegrasyonu (Web test) | Web UI test calistirma | 1g |
| D3 | Unit testler | Kalite güvencesi | 0.5g |
| D4 | README.md + dokumantasyon | Kullanim kilavuzu | 0.5g |
| D5 | End-to-end test (gercek bir task ile) | Dogrulama | 0.5g |

**Toplam tahmini sure: 11-15 gun**

---

## 10. Bagimliliklar

### Python Bagimliliklari

```
fastapi>=0.100.0
uvicorn>=0.20.0
httpx>=0.24.0
pydantic>=2.0.0
structlog>=23.0.0
pyyaml>=6.0
typer>=0.9.0
rich>=13.0.0
python-dotenv>=1.0.0
litellm>=1.40.0
jinja2>=3.1.0
```

### Harici Bagimliliklar

| Bilesen | Konum | Neden |
|---------|-------|-------|
| Graphify | `C:\repos\graphify-out` | Impact analysis |
| obiletcontext | `C:\repos\OBTaskManager\obiletcontext` | Domain knowledge |
| obilet-core-v2 | `C:\repos\obilet-core-v2` | Test edilecek kod |
| Docker Desktop | Local | Test ortami |
| GitHub Copilot lisansi | Sirket | LLM provider |

---

## 11. Riskler ve Azaltimlar

| Risk | Olasilik | Etki | Azaltim |
|------|----------|------|---------|
| Copilot rate limit | Orta | Yavas pipeline | Fallback modeller, retry logic |
| Docker ortam baslamaz | Dusuk | Test calismaz | Health check + retry + manual fallback |
| Graphify graph.json eski | Yuksek | Etki analizi eksik | Commit hash kontrolu, uyari |
| LLM halusinasyon | Orta | Yanlis senaryo | Human-in-the-loop onay |
| Test verisi uretilemez | Yuksek | Assertion anlamsiz | Stage ortam verisi kullan |
| Playwright flaky test | Orta | Yanlis fail | Retry mekanizması |
| obiletcontext eksik | Dusuk | Domain bilgisi zayif | codebase-retrieval fallback |

---

## 12. Basari Kriterleri

1. **Bir Jira task'tan 5 dakika icinde test senaryoları uretilebilmeli**
2. **API testleri otomatik calisip sonuc donmeli**
3. **Web UI'dan tum testlerin durumu takip edilebilmeli**
4. **Copilot lisansi disinda hicbir API key gerektirmemeli**
5. **Herhangi bir AI assistant'tan (opencode, Copilot, Claude) kullanilabilmeli**
6. **obiletcontext domain bilgisi kullanilarak anlamli assertion'lar uretilmeli**
7. **Graphify ile etki analizi dogru calismali**

---

## 13. Sonraki Adimlar

1. Bu plani incele ve onayla
2. `C:\repos\ob-test-intelligence` repo'sunu olustur
3. Faz A'yi baslat (DQG iskeletini kopyala)
4. LiteLLM config'i github_copilot/ ile yapilandir
5. Ilk end-to-end testi yap (ornek bir PDB task ile)
