---
sidebar_position: 5
title: "Git Entegrasyonu"
---

# Git Entegrasyonu

`GitClient` sınıfı, branch'ler arası fark analizi yapmak için yerel Git deposu üzerinde işlem yapar.

## Branch Temeli Bulma — `_find_base(branch)`

Verilen feature branch için karşılaştırma temeli (base branch) otomatik olarak tespit edilir.

### Base Adayları

Sadece şu branch'ler base adayı olarak değerlendirilir:

1. `preprod`
2. `stage`

**`main` branch hiçbir zaman base adayı olarak kullanılmaz.**

### Doğrulama

Her base adayı için commit sayısı kontrol edilir. Geçerli bir base için:

- Feature branch ile base arasındaki commit sayısı **1 ile 50 arasında** olmalıdır
- İlk geçerli base bulunca arama durur ve bu base döndürülür

## Değişen Dosyalar — `diff_files(branch)`

Feature branch ile base arasındaki dosya farklarını listeler:

```bash
git diff base...branch --name-only
```

Sonuçlar dosya yolları listesi olarak döner.

## Fark İçeriği — `diff_content(branch, max_chars=50000)`

Feature branch ile base arasındaki tam diff içeriğini çeker:

```bash
git diff base...branch -U2
```

`-U2` parametresi her değişiklik için 2 satır bağlam (context) gösterir.

**Karakter sınırı:** Diff çıktısı 50.000 karakter ile sınırlandırılır. Bu sınırı aşan içerik kesilir.

### Limiterler

| Veri Tipi | Maksimum Limit |
|---|---|
| Diff içeriği | 50.000 karakter |
| Dosya listesi | 200 dosya |
| Mimari bağlam | 20.000 karakter |

## Branch Kontrolü — `branch_exists(branch)`

Bir branch'in var olup olmadığını kontrol eder:

```bash
git rev-parse --verify <branch>
```

## Aktif Branch — `current_branch()`

Çalışma dizinindeki aktif branch adını döner:

```bash
git branch --show-current
```

## Boş Branch Koruması

Aşağıdaki durumlarda fonksiyonlar boş sonuç döner:

- Branch adı boş string ise
- Branch adı, base branch ile aynı ise

Bu koruma, anlamsız diff işlemlerinin önüne geçer.
