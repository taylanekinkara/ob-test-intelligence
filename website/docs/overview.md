---
sidebar_position: 1
title: Genel Bakış
---

# Genel Bakış

## ob-test-intelligence Nedir?

**ob-test-intelligence**, oBilet Core V2 (.NET seyahat platformu) için geliştirilmiş **yapay zeka destekli test pipeline'ıdır**. Jira görevlerini (PDB-XXXXX) okuyarak, git diff ile kod değişikliklerini analiz eder, hedeflenmiş test senaryoları üretir, yürütür ve doğrulama raporları oluşturur.

Tüm süreç **10 aşamalı bir pipeline** olarak tanımlanmıştır ve 2 kullanıcı onay noktasında duraklayarak insan-in-the-loop kontrolü sağlar.

---

## Neden İhtiyaç Var?

Manuel test süreçleri oBilet Core V2 gibi büyük ölçekli .NET seyahat platformlarında ciddi darboğazlar yaratmaktadır:

| Sorun | Açıklama |
|-------|----------|
| **Yavaş test yazılımı** | Her Jira görevi için manuel test senaryosu yazmak saatler sürer |
| **Kapsam eksikliği** | Manuel testte kenar durumlar (edge case) ve bağımlı modüller gözden kaçar |
| **Tutarsız kalite** | Farklı test mühendisleri farklı kalite standartları uygular |
| **Düşük geri bildirim** | Kod değişikliklerinin hangi modülleri etkilediği manuel olarak tahmin edilir |
| **Ölçeklenememe** | Artan görev sayısıyla test oranı doğrusal olarak artamaz |

**ob-test-intelligence** bu sorunları şu şekilde çözer:

- Kod değişikliklerini **otomatik analiz** eder ve etkilenen modülleri belirler
- **Graphify bilgi grafiği** ile 1-hop, 2-hop etki analizi yapar
- Yapay zeka ile **hedeflenmiş test senaryoları** üretir
- Testleri **otomatik yürütür** ve sonuçları doğrular
- **Token kullanımını** takip edererek maliyet kontrolü sağlar

---

## Nasıl Çalışır?

ob-test-intelligence, 10 aşamalı bir pipeline olarak çalışır. Her aşama bir öncekinin çıktısını girdi olarak alır. İki kullanıcı onay noktasında (`test_assess` ve `scenario_generate`) pipeline duraklar ve kullanıcı onayı bekler.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ob-test-intelligence Pipeline                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ ensure_ready │───▶│  task_read   │───▶│ code_analyze │───▶│impact_analyze│  │
│  │   (Hazırlık) │    │ (Jira Okuma) │    │ (Git Diff)   │    │  (Graphify)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘  │
│                                                                     │          │
│         ┌───────────────────────────────────────────────────────────┘          │
│         ▼                                                                      │
│  ┌──────────────┐         ┌───────────────────┐                               │
│  │ test_assess  │─── ⏸ ──▶│  Kullanıcı Onayı  │                               │
│  │ (Değerlendir)│         │   (Checkpoint 1)  │                               │
│  └──────┬───────┘         └─────────┬─────────┘                               │
│         │                           │                                          │
│         ▼                           ▼                                          │
│  ┌──────────────────┐    ┌────────────────────┐                               │
│  │scenario_generate │─── ⏸ ─▶│ Kullanıcı Onayı   │                               │
│  │ (Senaryo Üretim) │         │  (Checkpoint 2)   │                               │
│  └──────┬───────────┘         └─────────┬──────────┘                              │
│         │                               │                                        │
│         ▼                               ▼                                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────┐         │
│  │ env_prepare  │───▶│test_execute  │───▶│  verify  │───▶│  report  │         │
│  │ (Ortam Haz.) │    │ (Test Çalış) │    │(Doğrula) │    │ (Raporla)│         │
│  └──────────────┘    └──────────────┘    └──────────┘    └──────────┘         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

  ⏸ = Pipeline duraklar, kullanıcı onayı bekler (CLI üzerinden)
```

### Aşama Detayları

| Aşama | Fonksiyon | Açıklama |
|-------|-----------|----------|
| **ensure_ready** | Hazırlık | Ortam kontrolü, bağımlılık doğrulama, yapılandırma yükleme |
| **task_read** | Jira Okuma | PDB-XXXXX görevini Jira'dan okur (REST API → CLI → Stub fallback) |
| **code_analyze** | Kod Analizi | Base branch (preprod/stage) otomatik tespit, task branch ile diff |
| **impact_analyze** | Etki Analizi | Graphify bilgi grafiği ile 1-hop, 2-hop etki analizi, community ve god node tespiti |
| **test_assess** | Test Değerlendirme | Mevcut test kapsamını değerlendirir, öneri üretir ⏸ **Checkpoint 1** |
| **scenario_generate** | Senaryo Üretimi | LLM ile hedeflenmiş test senaryoları üretir ⏸ **Checkpoint 2** |
| **env_prepare** | Ortam Hazırlama | Test ortamını hazırlar, bağımlılıkları yapılandırır |
| **test_execute** | Test Yürütme | Senaryoları yürütür, sonuçları toplar |
| **verify** | Doğrulama | Test sonuçlarını doğrular, eksikleri belirler |
| **report** | Raporlama | Markdown rapor ve JSON çıktıları üretir |

---

## Temel Özellikler

### AI Destekli Test Üretimi

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  Git Diff    │────▶│  LLM (GLM)  │────▶│ Test Senaryoları │
│  Analizi    │     │  via litellm │     │  (Hedeflenmiş)  │
└─────────────┘     └─────────────┘     └─────────────────┘
       │                    │
       │                    ▼
       │            ┌─────────────┐
       │            │   z.ai API  │
       │            │  (Direkt)   │
       │            └─────────────┘
       ▼
┌─────────────────────────┐
│ Base Branch Otomatik    │
│ Tespiti (preprod/stage) │
└─────────────────────────┘
```

LLM olarak **z.ai GLM-5-turbo** kullanılır. `litellm` üzerinden direkt API çağrısı yapılır (proxy yok). Her çağrı için token kullanımı takip edilir.

### Otomatik Git Diff Analizi

- Base branch **otomatik olarak tespit edilir** (preprod veya stage)
- Task branch ile karşılaştırma yapılır
- Değişen dosyalar, fonksiyonlar ve bağımlılıklar belirlenir
- Sonuçlar `code-analysis.json` dosyasına kaydedilir

### Jira Entegrasyonu

```
┌──────────────┐     Başarılı      ┌──────────────┐
│  Jira REST   │───────────────────▶│   Veri       │
│     API      │                    │  Alındı      │
└──────┬───────┘                    └──────────────┘
       │ Başarısız
       ▼
┌──────────────┐     Başarılı      ┌──────────────┐
│   Jira CLI   │───────────────────▶│   Veri       │
│   Aracı      │                    │  Alındı      │
└──────┬───────┘                    └──────────────┘
       │ Başarısız
       ▼
┌──────────────┐
│    Stub      │────▶ Örnek/fixture veri ile devam
│   Fallback   │
└──────────────┘
```

Jira verisine erişim **3 katmanlı fallback** zinciri ile sağlanır: REST API → CLI → Stub.

### Graphify Bilgi Grafiği

Etki analizi için **Graphify** bilgi grafiği kullanılır:

| Analiz Türü | Açıklama |
|-------------|----------|
| **1-hop** | Doğrudan bağımlı modüller |
| **2-hop** | Dolaylı bağımlı modüller (transitive) |
| **Communities** | İlişkili modül grupları |
| **God Nodes** | Yüksek bağlantılı merkezi düğümler |

### Web UI Dashboard

```
┌─────────────────────────────────────────────────┐
│          FastAPI Web Dashboard                   │
│          localhost:8081                           │
│                                                   │
│  ┌─────────────┐  ┌─────────────┐               │
│  │   Pipeline   │  │    Test     │               │
│  │    Durumu    │  │  Senaryoları │               │
│  └─────────────┘  └─────────────┘               │
│                                                   │
│  ┌─────────────┐  ┌─────────────┐               │
│  │    Token     │  │   Rapor     │               │
│  │   Kullanımı  │  │   Görünümü  │               │
│  └─────────────┘  └─────────────┘               │
│                                                   │
│  ◉ Polling-based güncelleme                      │
└─────────────────────────────────────────────────┘
```

FastAPI tabanlı web arayüzü, **polling** yöntemiyle pipeline durumunu gerçek zamanlı gösterir.

### Token Takibi

Token kullanımı **her çağrı ve her aşama** için takip edilir:

```
┌──────────────────────────────────┐
│       Token Usage Tracking       │
├──────────────────────────────────┤
│                                  │
│  Per-Call  ──▶ Tekil LLM çağrısı│
│  Per-Phase ──▶ Aşama toplamları  │
│  Total     ──▶ Pipeline genel    │
│                                  │
│  Çıktı: token-usage.json         │
└──────────────────────────────────┘
```

### Anti-Pattern Tespiti

Kod analizi sırasında yaygın test anti-patternleri tespit edilir:

- TestWithoutAssertion
- AssertionOnMock
- HardCodedTestData
- OverMocking
- FlakyTestIndicator

---

## Kullanım Senaryoları

### Senaryo 1: Yeni Özellik Testi

Bir geliştirici PDB-12345 görevini tamamladığında, ob-test-intelligence otomatik olarak:

1. Görevi Jira'dan okur
2. Kod değişikliklerini analiz eder
3. Etkilenen modülleri belirler (Graphify)
4. Hedeflenmiş test senaryoları üretir
5. Testleri yürütür ve raporlar

### Senaryo 2: Refactoring Doğrulama

Mevcut kodda yapılan refactoring sonrası:

1. Tüm etkilenen modüller tespit edilir (1-hop, 2-hop)
2. Regresyon test senaryoları üretilir
3. Mevcut testlerin yeterliliği değerlendirilir
4. Eksik testler için öneriler sunulur

### Senaryo 3: Hata Düzeltme Testi

Bir bug fix sonrası:

1. Değişen kod ve etkilenen alanlar analiz edilir
2. Reproducibility senaryoları üretilir
3. Kenar durumlar (edge case) için ek testler önerilir
4. Düzeltmenin yan etki yaratmadığı doğrulanır

---

## Çıktılar

Her görev için ayrı bir dizin yapısı oluşturulur:

```
output/
└── PDB-XXXXX/
    ├── state.json                # Pipeline durum bilgisi
    ├── task-summary.json         # Jira görev özeti
    ├── code-analysis.json        # Git diff analizi sonuçları
    ├── impact-analysis.json      # Graphify etki analizi
    ├── test-assessment.json      # Test kapsam değerlendirmesi
    ├── test-scenarios.json       # Üretilen test senaryoları
    ├── test-results.json         # Test yürütme sonuçları
    ├── verification-report.json  # Doğrulama raporu (JSON)
    ├── report.md                 # Doğrulama raporu (Markdown)
    └── token-usage.json          # Token kullanım detayları
```

---

## Teknoloji Yığını

| Teknoloji | Sürüm | Kullanım Amacı |
|-----------|-------|----------------|
| **Python** | 3.14 | Ana programlama dili |
| **FastAPI** | - | Web UI ve API sunucusu (localhost:8081) |
| **Typer** | - | CLI framework |
| **Rich** | - | Terminal çıktı formatlama |
| **Pydantic** | - | Veri modelleme ve doğrulama |
| **litellm** | - | LLM API entegrasyonu (z.ai GLM-5-turbo) |
| **structlog** | - | Yapılandırılmış loglama |
| **PyYAML** | - | YAML yapılandırma dosyaları |
| **Graphify** | - | Bilgi grafiği ve etki analizi |

### Mimari Kararlar

| Karar | Seçim | Neden |
|-------|-------|-------|
| LLM Sağlayıcı | z.ai GLM-5-turbo | Maliyet-performans dengesi, Türkçe dil desteği |
| LLM Erişimi | litellm direkt API | Proxy katmanı gereksiz, düşük gecikme |
| CLI Framework | Typer + Rich | Tip güvenliği, zengin terminal çıktısı |
| Veri Modeli | Pydantic | Doğrulama, serileştirme, tip güvenliği |
| Web UI | FastAPI + polling | Hafif, hızlı, WebSocket karmaşıklığı yok |
| Jira Erişimi | REST API → CLI → Stub | Katmanlı fallback ile yüksek erişilebilirlik |
| Git Diff | Base branch otomatik tespit | preprod/stage arasında otomatik seçim |
| Loglama | structlog | JSON formatında yapılandırılmış loglar |
