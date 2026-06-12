---
sidebar_position: 8
title: "Web Dashboard"
---

# Web Dashboard

ob-test-intelligence, test sürecini gerçek zamanlı olarak izleyebileceğiniz yerleşik bir web arayüzü sunar.

## Mimari

Web arayüzü, **FastAPI** üzerine kurulmuştur. React veya başka bir frontend framework kullanılmaz; tüm HTML sayfaları sunucu tarafında oluşturulur ve JavaScript doğrudan HTML içinde yer alır.

### Kullanılan Teknolojiler

- **Backend:** FastAPI (Python)
- **Frontend:** Sunucu tarafında render edilen HTML + inline JavaScript
- **Tema:** Koyu tema (GitHub benzeri, `#0d1117` arka plan)
- **Sunucu:** Uvicorn

## Sayfalar

### Ana Sayfa (`/`)

Dashboard sayfası, tüm test görevlerini listeleyen bir tablo içerir.

| Sütun | Açıklama |
|-------|----------|
| Task Key | Jira/PDB görev anahtarı (ör. `PDB-12345`) |
| Phase | Mevcut pipeline aşaması |
| Updated | Son güncelleme zamanı |

Tablo, her 2 saniyede bir otomatik olarak yenilenir.

### Test Detay Sayfası (`/test/{task_key}`)

Her bir test görevi için detaylı bilgi sunar. Aşağıdaki bileşenleri içerir:

- **Aşama ilerleme çubuğu** — 10 pipeline aşamasını gösterir
- **Token kartları** — LLM kullanım istatistiklerini gösterir
- **Test öğeleri tablosu** — Değerlendirilen test senaryolarını listeler
- **Log görünümü** — Gerçek zamanlı log çıktıları

### Ayarlar Sayfası (`/settings`)

Uygulama ayarlarını yapılandırabileceğiniz sayfa.

## API Endpoint'leri

Web arayüzü, JSON formatında veri sunan aşağıdaki API endpoint'lerine sahiptir:

### `GET /api/status`

Uygulama durumunu döndürür.

```json
{
  "status": "ok"
}
```

### `GET /api/tests/{task_key}`

Belirtilen görev için tam pipeline durumunu (`PipelineState` JSON) döndürür.

### `GET /api/tests/{task_key}/logs?after=N`

Log girişlerini döndürür. `after` parametresi ile belirli bir satır numarasından sonraki loglar filtrelenebilir.

### `GET /api/tokens/{task_key}`

Token kullanım verilerini toplamlarıyla birlikte döndürür.

### `GET /api/test-items/{task_key}`

Test değerlendirmesi (assessment) ve üretilen senaryoların birleştirilmiş halini döndürür.

## Otomatik Yenileme (Polling)

Tüm sayfalarda veriler düzenli olarak yenilenir:

- **Yöntem:** JavaScript `setInterval`
- **Aralık:** 2000ms (2 saniye)
- **Kapsam:** Tablolar, kartlar, loglar ve ilerleme çubuğu dahil tüm bölümler

## Aşama İlerleme Çubuğu

Pipeline 10 aşamadan oluşur ve her aşama görsel olarak gösterilir:

| Durum | Renk | Davranış |
|-------|------|----------|
| Tamamlanmış (done) | Yeşil | Sabit |
| Mevcut (current) | Mavi | Pulse animasyonu |
| Bekleyen (pending) | Gri | Sabit |

## Token Kartları

4 adet kart, LLM kullanımını özetler:

1. **LLM Çağrıları** — Toplam çağrı sayısı
2. **Prompt Tokenları** — Giriş tokenlarının toplamı
3. **Completion Tokenları** — Çıkış tokenlarının toplamı
4. **Toplam** — Tüm tokenların toplamı

## Test Öğeleri Tablosu

Her test öğesi için aşağıdaki bilgiler listelenir:

| Sütun | Açıklama |
|-------|----------|
| ID | Test öğesi numarası |
| Hedef (Target) | Test edilen bileşen veya fonksiyon |
| Açıklama (Description) | Testin amacı |
| Tür (Type) | Test türü |
| Öncelik (Priority) | Öncelik seviyesi |

Her test öğesinin altında, ilişkili senaryolar bir alt tablo (sub-table) olarak gösterilir.

## Log Görünümü

Loglar, kaydırılabilir monospace bir `div` içinde gösterilir. Renk kodlaması aşağıdaki gibidir:

| Tür | Renk | Açıklama |
|-----|------|----------|
| `stage` | Mavi | Pipeline aşama geçişleri |
| `llm` | Mor | LLM çağrıları |
| `error` | Kırmızı | Hata mesajları |
| `artifact` | Yeşil | Üretilen dosyalar ve çıktılar |

## Tarayıcı Otomatik Açılışı

`_ensure_web_open()` fonksiyonu, web sunucusunu başlatır ve tarayıcıyı otomatik olarak açar:

1. Uvicorn `DETACHED_PROCESS` ve `CREATE_NEW_PROCESS_GROUP` bayraklarıyla başlatılır
2. `webbrowser` modülü ile varsayılan tarayıcıda http://localhost:8081 adresi açılır

Bu sayede CLI üzerinden `launch` veya `resume` komutu çalıştırıldığında tarayıcı otomatik olarak açılır ve kullanıcı manuel olarak URL girmek zorunda kalmaz.
