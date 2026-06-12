---
name: ob-test-intelligence
description: "oBilet test intelligence pipeline. Task-based test scenario generation, execution and verification. Use when user asks to test a task, run tests for PDB/JIRA key, or generate test scenarios."
---

# ob-test-intelligence

## On Hazirlik (Ilk Kurulum)

Pipeline'i ilk kez calistirmadan once, asagidaki komutu calistir:

```bash
python scripts/ob_test_run.py setup
```

Bu komut otomatik olarak:
1. `.venv` olusturur
2. `requirements.txt`'deki bagimliliklari kurar
3. `.env` dosyasi yoksa interaktif olarak olusturur:
   - OB_CORE_PATH (obilet-core-v2 repo path)
   - GRAPHIFY_PATH (graphify repo path)
   - CONTEXT_PATH (obiletcontext path)
   - OPENAI_API_KEY (z.ai API key)
   - Jira credentials (opsiyonel)
4. Kurulumu dogrular

Alternatif olarak, `.env.example`'i kopyalayip elle doldurabilirsin:
```bash
cp .env.example .env
```

## Kullanim

Kullanici bir task key verdiginde (ornek: "PDB-7910'u test et"), SADECE asagidaki adimlari uygula. Ekstra dosya okuma, path arama, glob yapma.

### Adim 0: On Hazirlik Kontrolu

Eger proje ilk kez calistiriliyorsa (`.venv` yoksa), once setup calistir:
```bash
python scripts/ob_test_run.py setup
```

### Adim 1: Jira verisini getir

```bash
python scripts/ob_test_run.py fetch-jira {TASK_KEY}
```

Bu komut otomatik olarak sirasiyla dener:
1. **Jira REST API** (.env icindeki OB_JIRA_* credential'lari ile)
2. **Jira CLI** (`jira` npm package, kuruluysa)
3. **Stub** (hicbiri calismazsa bos placeholder)

Sonuc: `outputs/tests/{TASK_KEY}/jira-raw.json`

### Adim 2: Pipeline'i baslat

```bash
python scripts/ob_test_run.py launch {TASK_KEY}
```

NOT: Pipeline jira-raw.json bulamazsa otomatik stub olusturur, durmaz.

### Adim 3: test_assess checkpoint

Pipeline `test_assess` fazinda durur. Kullaniciya ozet sun ve sor:
- "{TASK_KEY} icin {N} test maddesi belirlendi. Onayliyor musunuz?"

Kullanici "onayla" derse:
```bash
python scripts/ob_test_run.py resume {TASK_KEY} --response approve
```

### Adim 4: scenario_generate checkpoint

Pipeline `scenario_generate` fazinda durur. Kullaniciya ozet sun ve sor:
- "{TASK_KEY} icin {N} test senaryosu uretildi. Onayliyor musunuz?"

Kullanici "onayla" derse:
```bash
python scripts/ob_test_run.py resume {TASK_KEY} --response approve
```

### Adim 5: Rapor

Pipeline tamamlandiginda raporu oku ve kullaniciya sun:
```
outputs/tests/{TASK_KEY}/report.md
```

## OneMLI KURALLAR

1. **Ekstra dosya okuma YAPMA** - script'leri, config'leri okuma, sadece calistir
2. **Path arama YAPMA** - tum yollar otomatik tespit edilir
3. **Glob yapma** - gerekli dosyalar pipeline tarafindan uretilir
4. **Sadece bu adimlari takip et** - adim 0, 1, 2, 3, 4, 5 sirasiyla
5. **Her adimda kullanicidan onay al** - otomatik devam etme
6. **MCP tool kullanma** - Jira verisi icin sadece `fetch-jira` komutunu kullan
7. **Setup kontrolu** - .venv yoksa once setup calistir

## Loglama

Pipeline her calistirmada iki log dosyasi uretir:

| Dosya | Icerik |
|-------|--------|
| `outputs/tests/{TASK_KEY}/info.log` | Tum asama gecisleri, LLM cagrilari, artifact olusturma, zamanlama |
| `outputs/tests/{TASK_KEY}/error.log` | Tum hatalar, exception traceback'leri, LLM hatalari |

### info.log formati
```
2026-06-11T10:32:54 [STAGE_START] task_read started for PDB-7910
2026-06-11T10:32:54 [LLM] task_analyze model=openai/glm-5-turbo prompt=1200chars response=800chars duration=2500ms OK
2026-06-11T10:33:01 [STAGE_END] task_read OK for PDB-7910 (7000ms)
```

### error.log formati
```
2026-06-11T10:33:28 [ERROR] stage_code_analyze: GraphifyClient.impact_query() call failed
Traceback (most recent call last):
  File "src/app/stages/code_analyze.py", line 108, in stage_code_analyze
    ...
```

### Log kontrolleri
Pipeline tamamlandiginda, hata varsa error.log'u kontrol et:
```bash
Get-Content "outputs/tests/{TASK_KEY}/error.log"
```
