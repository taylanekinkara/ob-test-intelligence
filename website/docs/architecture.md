---
sidebar_position: 2
title: "Sistem Mimarisi"
---

# Sistem Mimarisi

ob-test-intelligence, modüler ve genişletilebilir bir pipeline mimarisi üzerine
inşa edilmiştir. Her bileşen tek bir sorumluluğa sahiptir ve stage'ler birbirinden
bağımsız olarak çalışabilir.

## Genel Bakış

```
+---------------------------+
|         CLI Layer         |   typer (cli.py)
|   launch / resume / poll  |
+-------------+-------------+
              |
              v
+---------------------------+
|       Web API Layer       |   FastAPI (web/app.py)
|   HTML + JSON Endpoints   |
+-------------+-------------+
              |
              v
+---------------------------+
|    Orchestrator Layer     |   PipelineOrchestrator
|   run / resume / state    |
+-------------+-------------+
              |
              v
+---------------------------+
|       Stage Layer         |   10 async stage modulu
|   analysis → generation   |
+-------------+-------------+
              |
              v
+---------------------------+
|    Integration Layer      |   LiteLLM / Git / Graphify
|   external service clients|
+-------------+-------------+
              |
              v
+---------------------------+
|    Configuration Layer    |   YAML + .env
|   app / model / thresholds|
+---------------------------+
```

---

## Katmanlar

### 1. CLI Katmani (cli.py)

CLI katmani [Typer](https://typer.tiangolo.com/) uzerinden sunulur. Kullanici
etkilesimi tamamen bu katman uzerinden gerceklesir.

```
+---------------------------------------------------+
|                    cli.py                          |
+---------------------------------------------------+
|  Komut       | Aciklama                           |
|--------------|------------------------------------|
| launch       | Pipeline'i baslatir                |
| resume       | Duraklatilmis pipeline'i devam     |
|              | ettirir                            |
| poll         | Web arayuzunu acar ve durumu       |
|              | takip eder                         |
| status       | Mevcut pipeline durumunu gosterir  |
| smoke        | Hizli saglik kontrolu yapar        |
+---------------------------------------------------+
```

**`_ensure_web_open` mekanizmasi:**

Web sunucusunun kesintisiz calismasi icin `DETACHED_PROCESS` flag'i ile
ayri bir surec olarak baslatilir. Bu sayede CLI komutu sonlansa bile web
sunucusu calismaya devam eder.

```python
DETACHED_PROCESS = 0x00000008
subprocess.Popen([sys.executable, "-m", "web.app"], creationflags=DETACHED_PROCESS)
```

### 2. Web API Katmani (FastAPI)

Web arayuzu [FastAPI](https://fastapi.tiangolo.com/) ile implemente
edilmistir. Hem HTML sayfa hem de JSON API endpoint'leri sunar.

```
+---------------------------------------------------+
|              web/app.py (FastAPI)                  |
+---------------------------------------------------+
| Endpoint              | Tur   | Aciklama          |
|-----------------------|-------|-------------------|
| /                     | HTML  | Ana sayfa, test   |
|                       |       | listesi           |
| /test/{key}           | HTML  | Test detay sayfasi|
| /api/status           | JSON  | Pipeline durumu   |
| /api/tests/{key}      | JSON  | Test senaryolari  |
| /api/logs/{key}       | JSON  | Log kayitlari     |
| /api/tokens/{key}     | JSON  | Token kullanimi   |
| /api/test-items/{key} | JSON  | Test maddeleri    |
+---------------------------------------------------+
```

**Polling-basli guncelleme:**

Istemci tarafinda WebSocket yerine polling kullanilir. Frontend belirli
araliklarla `/api/status` endpoint'ine istek gondererek durumu gunceller.

```
Tarayici                    Sunucu
   |                           |
   |--- GET /api/status ----->|
   |<-- 200 JSON {state} -----|
   |                           |
   |   (2 saniye bekle)        |
   |                           |
   |--- GET /api/status ----->|
   |<-- 200 JSON {state} -----|
   |                           |
```

### 3. Orchestrator Katmani (orchestrator.py)

`PipelineOrchestrator`, pipeline'in kalbidir. Stage'leri kaydeder, calistirir
ve durumunu yonetir.

```
+-----------------------------------------------------------+
|              PipelineOrchestrator                          |
+-----------------------------------------------------------+
|                                                           |
|  register_stage(name, fn)  -->  stages listesine ekler   |
|                                                           |
|  +-------------------+    +-------------------+          |
|  |   run()           |    |   resume()        |          |
|  |   - tum stage'ler |    |   - kayitli yerden|          |
|  |   - sira ile      |    |   - devam eder    |          |
|  |   - calistirilir  |    |   - state yuklenir|          |
|  +-------------------+    +-------------------+          |
|                                                           |
|  +-------------------+    +-------------------+          |
|  |   state persist   |    |   event callbacks |          |
|  |   - JSON dosyasi  |    |   - on_stage_start|          |
|  |   - her stage     |    |   - on_stage_end  |          |
|  |   |  sonrasi yaz  |    |   - on_error      |          |
|  +-------------------+    +-------------------+          |
|                                                           |
+-----------------------------------------------------------+
```

**`register_stage` pattern:**

Her stage bir isim ve async fonksiyon ile kaydedilir:

```
orchestrator.register_stage("code_analysis", run_code_analysis)
orchestrator.register_stage("test_generation", run_test_generation)
...
```

**Durum kaliciiligi (state persistence):**

Pipeline durumu her stage tamamlandiginda JSON dosyasina yazilir.
Bu sayede sistem cokmesi veya durdurma durumunda `resume()` ile
kaldigi yerden devam edebilir.

```json
{
  "current_stage": "test_generation",
  "completed_stages": ["task_summary", "code_analysis"],
  "artifacts": {
    "task_summary": "task-summary.json",
    "code_analysis": "code-analysis.json"
  }
}
```

**Olay geri cagrilari (event callbacks):**

```
+-------------------+     +--------------------------------+
| Orchestrator      |     | Callback alicilari             |
+-------------------+     +--------------------------------+
| on_stage_start    |---->| web socket bildirim, log       |
| on_stage_complete |---->| state persist, progress update  |
| on_error          |---->| hata logu, bildirim            |
+-------------------+     +--------------------------------+
```

### 4. Stage Katmani (stages/ dizini)

10 bagimsiz async fonksiyon icerir. Her stage onceki stage'in ciktisini
okur ve kendi ciktisini yazar.

```
+---------------------------------------------------+
|              stages/ dizini                        |
+---------------------------------------------------+
|  #  | Stage                  | Girdi              | Cikti                    |
|----|------------------------|--------------------|--------------------------|
|  1 | jira_fetch             | JIRA issue key     | jira-raw.json            |
|  2 | task_summary           | jira-raw.json      | task-summary.json        |
|  3 | code_analysis          | task-summary.json  | code-analysis.json       |
|  4 | impact_analysis        | code-analysis.json | impact-analysis.json     |
|  5 | test_assessment        | impact-analysis    | test-assessment.json     |
|  6 | test_scenario_gen      | test-assessment    | test-scenarios.json      |
|  7 | test_execution         | test-scenarios     | test-results.json        |
|  8 | verification           | test-results       | verification-report.json |
|  9 | report_generation      | verification       | report.md                |
| 10 | notification           | report.md          | bildirim gonderimi       |
+---------------------------------------------------+
```

Her stage'in internal yapisi:

```
+-------------------------------------------+
|            Stage Fonksiyonu                |
+-------------------------------------------+
|                                           |
|  1. Onceki artifact'i oku                 |
|     artifact = read_artifact(prev_stage)  |
|                                           |
|  2. Islemi gerceklestir                   |
|     result = await process(artifact)      |
|                                           |
|  3. Yeni artifact'i yaz                   |
|     write_artifact(stage_name, result)    |
|                                           |
|  4. State'i guncelle                      |
|     update_state(stage_name, COMPLETE)    |
|                                           |
+-------------------------------------------+
```

### 5. Entegrasyon Katmani

Dis servislerle iletisimden sorumlu istemci siniflari.

#### LiteLLMClient (litellm_client.py)

LLM cagrilari icin kullanilan async istemci.

```
+-----------------------------------------------------------+
|                  LiteLLMClient                             |
+-----------------------------------------------------------+
|                                                           |
|  async completion(messages, model, **kwargs)              |
|     |                                                     |
|     +--> token tracking (prompt + completion tokens)      |
|     |                                                     |
|     +--> rate limit retry:                                |
|           - maksimum 3 deneme                             |
|           - exponential backoff                           |
|           - deneme 1: 1s, deneme 2: 2s, deneme 3: 4s    |
|                                                           |
|  token_tracking                                           |
|     +--> toplam token sayisi                              |
|     +--> maliyet hesaplama                                |
|                                                           |
+-----------------------------------------------------------+
```

**Retry mekanizmasi:**

```
Deneme 1  ---[rate limit hatasi]---> 1 saniye bekle --> Deneme 2
Deneme 2  ---[rate limit hatasi]---> 2 saniye bekle --> Deneme 3
Deneme 3  ---[rate limit hatasi]---> 4 saniye bekle --> Hata firlat
```

#### GitClient (git_client.py)

Git repository islemleri icin kullanilan istemci.

```
+-----------------------------------------------------------+
|                    GitClient                               |
+-----------------------------------------------------------+
|                                                           |
|  diff_files(base, head)       --> degisen dosya listesi   |
|  diff_content(base, head)     --> detayli diff icerigi    |
|  branch_exists(name)          --> branch varlik kontrolu  |
|                                                           |
|  _find_base()                                            |
|     |                                                    |
|     +--> 1. "preprod" branch'ini dene                    |
|     +--> 2. "stage" branch'ini dene                      |
|     +--> 3. maksimum 50 commit geriye don                |
|                                                           |
+-----------------------------------------------------------+
```

**`_find_base` algoritmasi:**

```
_find_base()
    |
    v
+------------------+
| "preprod" var mi?|--evet--> preprod'u kullan
+--------+---------+
         | hayir
         v
+------------------+
| "stage" var mi?  |--evet--> stage'i kullan
+--------+---------+
         | hayir
         v
+------------------+
| HEAD~50'yi kullan|  (fallback)
+------------------+
```

#### GraphifyClient

Graphify servisi ile iletisim icin kullanilan istemci. Test iliskileri
ve bagimlik analizi icin graph veri yapisini sorgular.

### 6. Konfigurasyon Katmani

Tum ayarlar YAML dosyalari ve `.env` uzerinden yonetilir.

```
+---------------------------------------------------+
|          Konfigurasyon Dosyalari                   |
+---------------------------------------------------+
| Dosya                  | Icerik                    |
|------------------------|---------------------------|
| app.yaml               | Genel uygulama ayarlari   |
|                        | - log seviyesi            |
|                        | - output dizini           |
|                        | - timeout degerleri       |
| model_routing.yaml     | LLM model yonlendirme     |
|                        | - stage -> model eslemesi |
|                        | - temperature ayarlari    |
|                        | - max_tokens limitleri    |
| thresholds.yaml        | Esik degerleri            |
|                        | - guven skorlari          |
|                        | - kapsam yuzdeleri        |
|                        | - basari kriterleri       |
| .env                   | Ortam degiskenleri        |
|                        | - API anahtarlari         |
|                        | - JIRA credentials        |
|                        | - endpoint URL'leri       |
+---------------------------------------------------+
```

**AppConfig (config.py) - Singleton pattern:**

```python
class AppConfig:
    _instance = None

    @classmethod
    def get(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._load_yaml_configs()
        self._find_paths_auto()
```

```
+-----------------------------------------------------------+
|              AppConfig (Singleton)                         |
+-----------------------------------------------------------+
|                                                           |
|  _load_yaml_configs()                                     |
|     +--> app.yaml yukle                                   |
|     +--> model_routing.yaml yukle                         |
|     +--> thresholds.yaml yukle                            |
|                                                           |
|  _find_paths_auto()                                       |
|     +--> proje kokugu bul                                 |
|     +--> output dizinini olustur                          |
|     +--> artifact dizinlerini hazirla                     |
|                                                           |
|  Ozellikler:                                              |
|     +--> app: genel ayarlar                               |
|     +--> models: model routing konfigi                    |
|     +--> thresholds: esik degerleri                       |
|                                                           |
+-----------------------------------------------------------+
```

---

## Veri Akisi (Data Flow)

Pipeline boyunca her stage bir oncekinin ciktisini girdi olarak alir
ve sirali bir veri akisi olusturur.

```
JIRA Issue Key
       |
       v
+---------------+     +------------------+     +-------------------+
| jira-raw.json |---->|task-summary.json |---->|code-analysis.json |
+---------------+     +------------------+     +-------------------+
                                                        |
                                                        v
+-------------+   +---------------------+   +-------------------+
| report.md   |<--|verification-report  |<--|test-results.json  |
|             |   |      .json          |   |                   |
+-------------+   +---------------------+   +-------------------+
       ^                   ^                         ^
       |                   |                         |
+-------------+   +---------------------+   +-------------------+
|   report    |   |test-assessment.json |   |test-scenarios.json|
| generation  |   |                     |   |                   |
+-------------+   +---------------------+   +-------------------+
                          ^
                          |
                +-------------------+
                |impact-analysis    |
                |     .json         |
                +-------------------+
```

### Detayli Veri Akisi

```
Stage                 Girdi Dosyasi          Cikti Dosyasi
--------------------- ---------------------- ---------------------------
jira_fetch            (JIRA API)             jira-raw.json
task_summary          jira-raw.json          task-summary.json
code_analysis         task-summary.json      code-analysis.json
impact_analysis       code-analysis.json     impact-analysis.json
test_assessment       impact-analysis.json   test-assessment.json
test_scenario_gen     test-assessment.json   test-scenarios.json
test_execution        test-scenarios.json    test-results.json
verification          test-results.json      verification-report.json
report_generation     verification-report    report.md
```

---

## Pydantic Semalari (schemas.py)

Veri modelleri [Pydantic](https://docs.pydantic.dev/) ile tanimlanmistir.
Tip guvenligi ve dogrulama saglar.

```python
class PipelineState(BaseModel):
    """Pipeline genel durum modeli"""
    current_stage: str
    completed_stages: list[str]
    artifacts: dict[str, str]
    started_at: datetime | None
    updated_at: datetime | None

class CodeAnalysisResult(BaseModel):
    """Kod analizi sonuc modeli"""
    changed_files: list[str]
    functions_affected: list[str]
    dependencies: list[str]
    risk_level: str

class TestAssessment(BaseModel):
    """Test degerlendirme modeli"""
    coverage_required: float
    priority_areas: list[str]
    test_types: list[str]

class TestScenario(BaseModel):
    """Test senaryo modeli"""
    scenario_id: str
    title: str
    steps: list[str]
    expected_result: str
    priority: str

class TestResult(BaseModel):
    """Test sonuc modeli"""
    scenario_id: str
    status: str
    actual_result: str
    duration_ms: int

class VerificationReport(BaseModel):
    """Dogrulama rapor modeli"""
    total_scenarios: int
    passed: int
    failed: int
    skipped: int
    coverage_percent: float
```

### Model Iliskileri

```
+------------------+
| PipelineState    |
|  - current_stage |
|  - completed[]   |
|  - artifacts{}   |
+------------------+
         |
         | references
         v
+------------------+     +-------------------+
| CodeAnalysis     |---->| TestAssessment     |
|  Result          |     |  - coverage_req   |
|  - changed_files |     |  - priority_areas |
|  - functions     |     |  - test_types     |
|  - dependencies  |     +-------------------+
|  - risk_level    |              |
+------------------+              | informs
                                  v
                         +-------------------+
                         | TestScenario       |
                         |  - scenario_id    |
                         |  - title          |
                         |  - steps[]        |
                         |  - expected       |
                         |  - priority       |
                         +-------------------+
                                  |
                                  | produces
                                  v
                         +-------------------+
                         | TestResult         |
                         |  - scenario_id    |
                         |  - status         |
                         |  - actual_result  |
                         |  - duration_ms    |
                         +-------------------+
                                  |
                                  | aggregates
                                  v
                         +-------------------+
                         | VerificationReport |
                         |  - total          |
                         |  - passed         |
                         |  - failed         |
                         |  - skipped        |
                         |  - coverage %     |
                         +-------------------+
```

---

## Hata Yonetimi

### Stage Hata Davranisi

```
+------------------+     Basarili     +------------------+
| Stage Calisiyor  |---------------->| Sonraki Stage    |
+--------+---------+                 +------------------+
         |
         | Hata
         v
+------------------+     Retry basarili +------------------+
| Retry Mekanizmasi|----------------->| Sonraki Stage    |
+--------+---------+                  +------------------+
         |
         | Retry basarisiz
         v
+------------------+
| State Kaydet     |
| (hata durumu)    |
+--------+---------+
         |
         v
+------------------+
| resume() ile     |
| devam edilebilir |
+------------------+
```

### Token Kullanim Takibi

Her LLM cagrisi sonrasi token kullanimi kaydedilir:

```
+---------------------------------------------+
|           Token Tracking                     |
+---------------------------------------------+
|                                             |
|  stage          prompt    completion  toplam |
|  -------------  -------   ----------  -----  |
|  task_summary   1,250     340         1,590  |
|  code_analysis  3,800     1,200       5,000  |
|  test_gen       2,100     890         2,990  |
|  ...            ...       ...         ...    |
|  -------------  -------   ----------  -----  |
|  TOPLAM         7,150     2,430       9,580  |
|                                             |
+---------------------------------------------+
```

---

## Dizin Yapisi

```
ob-test-intelligence/
|
+-- cli.py                    # CLI giris noktasi
+-- config.py                 # AppConfig singleton
+-- orchestrator.py           # PipelineOrchestrator
+-- schemas.py                # Pydantic modelleri
+-- litellm_client.py         # LLM istemcisi
+-- git_client.py             # Git istemcisi
|
+-- stages/                   # Stage modulleri
|   +-- __init__.py
|   +-- jira_fetch.py
|   +-- task_summary.py
|   +-- code_analysis.py
|   +-- impact_analysis.py
|   +-- test_assessment.py
|   +-- test_scenario_gen.py
|   +-- test_execution.py
|   +-- verification.py
|   +-- report_generation.py
|   +-- notification.py
|
+-- web/                      # FastAPI web arayuzu
|   +-- app.py                # Ana uygulama
|   +-- static/               # Statik dosyalar
|   +-- templates/            # HTML sablonlari
|
+-- config/                   # YAML konfigurasyon
|   +-- app.yaml
|   +-- model_routing.yaml
|   +-- thresholds.yaml
|
+-- .env                      # Ortam degiskenleri
+-- website/                  # Docusaurus dokumantasyon
```
