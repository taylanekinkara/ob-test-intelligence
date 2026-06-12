---
sidebar_position: 6
title: "LLM Entegrasyonu"
---

# LLM Entegrasyonu

`LiteLLMClient` sınıfı, LiteLLM kütüphanesi üzerinden LLM çağrıları yapar. Proxy sunucu kullanılmaz; doğrudan API çağrısı yapılır.

## Model ve API

| Ayar | Değer |
|---|---|
| Model | `openai/glm-5-turbo` |
| API Sağlayıcı | z.ai |
| Base URL | `https://api.z.ai/api/paas/v4/` |

LiteLLM'in `acompletion()` fonksiyonu doğrudan çağrılır. Arada bir proxy sunucu bulunmaz.

## Parametre Yönetimi

Desteklenmeyen parametrelerin hata vermemesi için:

```python
litellm.drop_params = True
```

Bu ayar, LiteLLM'in model tarafından desteklenmeyen parametreleri sessizce yok saymasını sağlar.

## Rate Limit ve Yeniden Deneme

API rate limit'e takılırsa otomatik yeniden deneme mekanizması çalışır:

| Ayar | Değer |
|---|---|
| Maksimum deneme | 3 |
| Backoff stratejisi | Üstel (exponential) |
| Bekleme süresi | `5s × deneme_sayısı` |

Örnek: 1. deneme → 5 sn bekle, 2. deneme → 10 sn bekle, 3. deneme → 15 sn bekle.

## Token Takibi

Her LLM çağrısında token kullanımı takip edilir:

1. **Çağrı başına:** `response.usage` alanından `prompt_tokens` ve `completion_tokens` çıkarılır
2. **Bellek içi takip:** `_token_cache` sözlüğünde her çağrının token verisi saklanır
3. **Kalıcı kayıt:** Her çağrıdan sonra `token-usage.json` dosyasına yazılır

### Token Özeti — `get_token_summary()`

Tüm çağrıların toplam token kullanımını döner:

- Toplam prompt tokens
- Toplam completion tokens
- Toplam çağrı sayısı

## Sağlık Kontrolü

`health_check()` metodu, modelin erişilebilir olduğunu doğrular:

- Modele `"ping"` mesajı gönderilir
- Yanıt alınması durumunda sistem sağlıklı kabul edilir
- Hata durumunda exception fırlatılır

Bu kontrol, pipeline başlamadan önce LLM servisinin可用 olduğundan emin olmak için kullanılır.
