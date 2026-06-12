---
sidebar_position: 12
title: "Token Takibi"
---

# Token Takibi

ob-test-intelligence, her LLM çağrısının token kullanımını detaylı olarak takip eder. Bu sayede maliyet analizi yapabilir ve API kullanımınızı optimize edebilirsiniz.

## Genel Bakış

Pipeline çalışırken yapılan **her LLM çağrısı** otomatik olarak kaydedilir. Takip edilen bilgiler:

| Alan | Açıklama |
|------|----------|
| `phase` | Çağrının yapıldığı pipeline aşaması |
| `model` | Kullanılan LLM modeli |
| `prompt_tokens` | Giriş (prompt) token sayısı |
| `completion_tokens` | Çıkış (completion) token sayısı |
| `total_tokens` | Toplam token sayısı |

## Veri Depolama

### Bellek İçi Önbellek

Token verileri, her görev anahtarı (`task_key`) için bellekte bir `_token_cache` sözlüğünde tutulur:

```python
_token_cache: dict[str, TokenUsage] = {}
```

### Kalıcı Depolama

Her LLM çağrısından sonra veriler **`token-usage.json`** dosyasına yazılır. Bu sayede:

- Pipeline yeniden başlasa bile veriler korunur
- Geçmiş çalıştırmaların token kullanımı incelenebilir
- Uygulama çökse bile veri kaybı yaşanmaz

## Veri Yapısı

`token-usage.json` dosyasının yapısı:

```json
{
  "task_key": "PDB-12345",
  "calls": [
    {
      "phase": "code_analysis",
      "model": "gpt-4o",
      "prompt_tokens": 1500,
      "completion_tokens": 800,
      "total_tokens": 2300
    }
  ],
  "totals": {
    "total_prompt_tokens": 15000,
    "total_completion_tokens": 8500,
    "total_tokens": 23500,
    "total_calls": 12,
    "estimated_cost_usd": 0.47
  }
}
```

### Totals Alanı

| Alan | Açıklama |
|-----|----------|
| `total_prompt_tokens` | Tüm çağrıların prompt token toplamı |
| `total_completion_tokens` | Tüm çağrıların completion token toplamı |
| `total_tokens` | Tüm tokenların toplamı |
| `total_calls` | Toplam LLM çağrı sayısı |
| `estimated_cost_usd` | Tahmini maliyet (USD) |

## Log Formatı

Her LLM çağrısı loglandığında aşağıdaki format kullanılır:

```
tokens=NNN(pp+cc)
```

Burada:
- **NNN** = toplam token sayısı
- **pp** = prompt token sayısı
- **cc** = completion token sayısı

**Örnek:**

```
tokens=2300(1500+800)
```

Bu, toplam 2300 token kullanıldığını, bunun 1500'ünün prompt ve 800'ünün completion tokenları olduğunu gösterir.

## Web Arayüzünde Token Kullanımı

Web dashboard'da token kullanımı **4 kart** halinde gösterilir:

| Kart | Açıklama |
|------|----------|
| **LLM Çağrıları** | Toplam çağrı sayısı |
| **Prompt Tokenları** | Giriş tokenlarının toplamı |
| **Completion Tokenları** | Çıkış tokenlarının toplamı |
| **Toplam** | Tüm tokenların toplamı |

Kartlar her 2 saniyede bir otomatik olarak güncellenir.

## API Erişimi

Token verilerine programatik olarak erişmek için:

### `GET /api/tokens/{task_key}`

Belirtilen görev için tam token kullanım verisini döndürür. Yanıt, `calls` dizisi ve `totals` nesnesini içerir.

**Örnek istek:**

```bash
curl http://localhost:8081/api/tokens/PDB-12345
```

## Rapor

Her test çalıştırmasının sonucu olan `report.md` dosyasında token kullanım tablosu yer alır. Bu tablo, aşama bazında token kullanımını ve toplam maliyeti gösterir.

## Programatik Erişim

`get_token_summary()` fonksiyonu ile Python kodu üzerinden token kullanım verilerine erişebilirsiniz:

```python
from app.token_tracker import get_token_summary

summary = get_token_summary("PDB-12345")
print(f"Toplam çağrı: {summary['totals']['total_calls']}")
print(f"Toplam token: {summary['totals']['total_tokens']}")
print(f"Tahmini maliyet: ${summary['totals']['estimated_cost_usd']}")
```

Bu fonksiyon, öncelikle bellek önbelleğine bakar; yoksa `token-usage.json` dosyasından verileri yükler.
