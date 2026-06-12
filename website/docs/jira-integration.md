---
sidebar_position: 4
title: "Jira Entegrasyonu"
---

# Jira Entegrasyonu

`fetch_jira.py` scripti, Jira verilerini üç kademeli bir fallback zinciri ile çeker:

```
REST API → Jira CLI → Stub
```

Her kademe başarısız olursa, bir sonrakine geçilir.

## REST API (Birinci Öncelik)

Doğrudan Jira REST API kullanılır. Aşağıdaki ortam değişkenlerini gerektirir:

| Ortam Değişkeni | Açıklama |
|---|---|
| `OB_JIRA_BASE_URL` | Jira sunucu adresi |
| `OB_JIRA_EMAIL` | Kullanıcı e-postası |
| `OB_JIRA_API_TOKEN` | API token |

Çağrılan endpoint'ler:

- **Issue verileri:** `/rest/api/2/issue/{key}`
- **Yorumlar:** `/rest/api/2/issue/{key}/comment`
- **Geliştirme bilgisi:** `/rest/devops/1.0/issue/{key}/devInfo`

## CLI Fallback (İkinci Öncelik)

REST API kullanılamadığında Jira CLI aracı tetiklenir:

```bash
jira issue view {key} --format json
```

CLI çıktısı parse edilerek REST API ile aynı yapıda veri elde edilir.

## Stub Fallback (Son Çare)

Hem REST API hem CLI başarısız olursa, boş bir stub nesne oluşturulur:

- `issue` — boş gövde
- `comments` — boş liste
- `dev_info` — boş nesne

Bu sayede pipeline hata vermeden devam edebilir.

## ADF (Atlassian Document Format) Parse

Jira issue açıklamaları ve yorumlar ADF formatında gelir. `_extract_text_from_adf()` fonksiyonu, ADF dokümanını özyinelemeli olarak gezer ve düğümlerden düz metin çıkarır.

ADF ağacındaki her `text` düğümünün içeriği birleştirilir ve alt içerikler (`content` alanı) derinlemesine işlenir.

## Alan Tespiti (Domain Detection)

Issue başlığı, açıklaması ve yorumları üzerinden hangi iş alanını (domain) ilgilendirdiği tespit edilir. `_DOMAIN_KEYWORDS` sözlüğü, her alan için Türkçe ve İngilizce anahtar kelimeler içerir:

| Alan | Örnek Anahtar Kelimeler |
|---|---|
| `bus` | otobüs, bus, bilet, sefer |
| `flight` | uçak, flight, havayolu, uçuş |
| `hotel` | otel, hotel, konaklama, accommodation |
| `sea` | deniz, sea, ferry, feribot |
| `payment` | ödeme, payment, POS, ödeme |
| `rentacar` | kiralık, rent, araç, car |
| `transfer` | transfer, aktarma, shuttle |

Anahtar kelime eşleşmelerine göre issue ilgili alan(lar)a atanır.

## Branch Tespiti

Geliştirme bilgisinden (`dev_info`) branch adı çıkarılır:

1. **branches** alanından doğrudan branch bilgisi alınır
2. **pullRequests** içindeki `headRefName` alanından branch adı çıkarılır

Tespit edilen branch adı, Git entegrasyonunda diff alınması için kullanılır.

## Çıktı

Tüm toplanan veriler `jira-raw.json` dosyasına yazılır:

```json
{
  "issue": { "...": "..." },
  "comments": [ "...", "..." ],
  "dev_info": { "...": "..." }
}
```

Bu dosya, pipeline'ın sonraki aşamalarında (etki analizi, test senaryosu üretimi vb.) girdi olarak kullanılır.
