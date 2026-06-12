---
sidebar_position: 11
title: "Yapılandırma"
---

# Yapılandırma

oBilet Test Intelligence, YAML yapılandırma dosyaları, ortam değişkenleri ve prompt şablonları üzerinden yapılandırılır.

## `app.yaml`

Ana uygulama yapılandırma dosyası.

### `app`

```yaml
app:
  name: ob-test-intelligence
  host: 127.0.0.1
  port: 8501
```

| Alan    | Açıklama                          |
| ------- | --------------------------------- |
| `name`  | Uygulama adı                      |
| `host`  | Web sunucusu dinleme adresi       |
| `port`  | Web sunucusu dinleme portu        |

### `paths`

```yaml
paths:
  ob_core: C:/repos/obilet-core-v2
  graphify: C:/repos/graphify-out
  context: C:/repos/obiletcontext
  outputs: ./outputs
```

| Alan        | Açıklama                                      |
| ----------- | --------------------------------------------- |
| `ob_core`   | oBilet core projesinin kök dizini             |
| `graphify`  | Graphify çıktı grafiğinin bulunduğu dizin     |
| `context`   | oBilet context dosyalarının bulunduğu dizin   |
| `outputs`   | Pipeline çıktılarının yazılacağı dizin        |

### `pipeline.profiles.standard`

```yaml
pipeline:
  profiles:
    standard:
      phases:
        - task_fetch
        - task_analyze
        - code_analyze
        - impact_assess
        - test_assess
        - test_assess_user
        - scenario_generate
        - scenario_review_user
        - test_create
        - report
      user_checkpoints:
        - test_assess
        - scenario_generate
```

| Alan               | Açıklama                                                                 |
| ------------------- | ----------------------------------------------------------------------- |
| `phases`            | Pipeline aşamalarının sıralı listesi (toplam 10 aşama)                   |
| `user_checkpoints`  | Kullanıcı onayı bekleyen aşamalar (`test_assess`, `scenario_generate`)   |

### `docker`

```yaml
docker:
  image: ob-test-intelligence:latest
  build_context: .
```

Konteyner yapılandırma ayarları.

---

## `model_routing.yaml`

LLM model yönlendirme yapılandırması.

### `routing`

Her pipeline aşamasının hangi model grubunu kullanacağını belirler.

```yaml
routing:
  task_analyze: analyzer
  code_analyze: analyzer
  impact_assess: analyzer
  test_assess: analyzer
  scenario_generate: analyzer
  scenario_review: analyzer
  test_create: analyzer
  report: analyzer
```

### `model_groups`

Model grupları ve kullanılan model adlarını tanımlar.

```yaml
model_groups:
  analyzer:
    model: openai/glm-5-turbo
```

**Mevcut durum:** Tüm aşamalar `analyzer` grubunu kullanmakta olup, bu grup `openai/glm-5-turbo` modeline yönlendirilmiştir.

---

## `thresholds.yaml`

Risk, kapsam ve etki eşik yapılandırması.

### Risk Eşikleri

```yaml
risk:
  high: 0.8
  medium: 0.5
  low: 0.2
```

### Kapsam Eşikleri

```yaml
coverage:
  minimum: 0.7
  target: 0.9
```

### Etki Yapılandırması

```yaml
impact:
  critical_weight: 3.0
  major_weight: 2.0
  minor_weight: 1.0
```

| Alan              | Açıklama                                        |
| ----------------- | ----------------------------------------------- |
| `risk`            | Risk seviyelerinin eşik değerleri               |
| `coverage`        | Minimum ve hedef test kapsamı oranları          |
| `impact`          | Etki ağırlıkları (kritik, büyük, küçük)         |

---

## `.env`

Ortam değişkenleri yapılandırması.

### Jira Bağlantısı

| Değişken             | Açıklama                              |
| -------------------- | ------------------------------------- |
| `OB_JIRA_BASE_URL`   | Jira sunucu temel URL'si              |
| `OB_JIRA_EMAIL`      | Jira kullanıcı e-postası              |
| `OB_JIRA_API_TOKEN`  | Jira API erişim belirteci             |

### Proje Yolları

| Değişken        | Açıklama                                     |
| --------------- | -------------------------------------------- |
| `OB_CORE_PATH`  | oBilet core proje dizini                     |
| `GRAPHIFY_PATH` | Graphify çıktı dizini                        |
| `CONTEXT_PATH`  | oBilet context dizini                        |

### Sunucu Portu

| Değişken   | Açıklama                  |
| ---------- | ------------------------- |
| `WEB_PORT` | Web arayüzü portu         |
| `API_PORT` | API sunucusu portu        |

### LLM Yapılandırması

| Değişken            | Açıklama                                            |
| ------------------- | --------------------------------------------------- |
| `LITELLM_MASTER_KEY` | LiteLLM proxy anahtarı                             |
| `PIPELINE_PROFILE`  | Kullanılacak pipeline profili (varsayılan: `standard`) |
| `LLM_PROFILE`       | LLM yapılandırma profili                            |

### OpenAI / z.ai

| Değişken           | Açıklama                                          |
| ------------------ | ------------------------------------------------- |
| `OPENAI_API_KEY`   | z.ai platformu için API anahtarı                  |
| `OPENAI_BASE_URL`  | `https://api.z.ai/api/paas/v4/`                   |

---

## `config/prompts/`

Pipeline aşamalarında kullanılan Markdown tabanlı prompt şablonları.

| Dosya                    | Açıklama                                    |
| ------------------------ | ------------------------------------------- |
| `task_analyzer.md`       | Görev analiz aşaması prompt şablonu         |
| `code_analyzer.md`       | Kod analizi aşaması prompt şablonu          |
| `impact_assessor.md`     | Etki değerlendirmesi prompt şablonu         |
| `test_assessor.md`       | Test değerlendirmesi prompt şablonu         |
| `scenario_generator.md`  | Senaryo üretimi prompt şablonu              |

Her dosya standart Markdown formatındadır ve `{placeholder}` sözdizimini kullanarak dinamik değişkenler içerir. Pipeline çalıştırıldığında bu yer tutucular gerçek verilerle değiştirilir.

Örnek placeholder'lar:

- `{task_key}` — Jira görev anahtarı
- `{task_summary}` — Görev özeti
- `{task_description}` — Görev açıklaması
- `{code_context}` — İlgili kod parçaları
- `{impact_data}` — Etki analizi sonuçları

---

## Pipeline Profilleri

Şu anda yalnızca **`standard`** profili tanımlıdır.

### Standard Profil Aşamaları

| #  | Aşama                  | Kullanıcı Checkpoint |
| -- | ---------------------- | -------------------- |
| 1  | `task_fetch`           | Hayır                |
| 2  | `task_analyze`         | Hayır                |
| 3  | `code_analyze`         | Hayır                |
| 4  | `impact_assess`        | Hayır                |
| 5  | `test_assess`          | **Evet**             |
| 6  | `test_assess_user`     | Hayır                |
| 7  | `scenario_generate`    | **Evet**             |
| 8  | `scenario_review_user` | Hayır                |
| 9  | `test_create`          | Hayır                |
| 10 | `report`               | Hayır                |

Toplam **10 aşama** ve **2 kullanıcı checkpoint** bulunmaktadır.

---

## Yol Otomatik Algılama

`app.yaml` içindeki `paths` değerleri veya `.env` ortam değişkenleri belirtilmediğinde, sistem aşağıdaki dizinleri sırasıyla tarar:

1. `C:/repos/`
2. `~/repos/`
3. `~/projects/`

Her dizin içinde şu klasörler aranır:

| Aranan Klasör         | Karşılık Gelen Yol  |
| --------------------- | ------------------- |
| `obilet-core-v2`      | `ob_core`           |
| `graphify-out`        | `graphify`          |
| `obiletcontext`       | `context`           |

İlk bulunan eşleşme kullanılır. Birden fazla dizinde aynı klasör varsa, arama sırasına göre ilk sonuç önceliklidir.
