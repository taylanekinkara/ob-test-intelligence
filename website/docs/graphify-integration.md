---
sidebar_position: 7
title: "Graphify Entegrasyonu"
---

# Graphify Entegrasyonu

oBilet Test Intelligence, kod bağımlılık grafiğini analiz etmek için **Graphify** bilgi grafiğini (knowledge graph) kullanır.

## Veri Kaynağı

`graphify-out` dizini, Graphify tarafından oluşturulan `graph.json` dosyasını içerir. Bu dosya, projenin modülleri, bileşenleri ve aralarındaki bağımlılıkları temsil eden bir bilgi grafiğidir.

## GraphifyClient

`GraphifyClient` sınıfı, bilgi grafiği üzerinde sorgulama yapar. Değişen dosyaların etki alanını belirlemek için kullanılır.

## Etki Analizi (Impact Analysis)

`impact_analyze` aşamasında, değişen dosyalar üzerinden etki analizi yapılır. Analiz dört katmanlıdır:

```
Seed dosyalar → 1-hop komşular → 2-hop komşular → Topluluklar → God node'lar
```

### 1. Seed Dosyalar

Doğrudan değişen dosyalar. Git diff'ten elde edilen dosya listesidir.

### 2. 1-Hop Komşular

Seed dosyaların doğrudan bağımlılıkları ve kendilerine bağımlı olan dosyalar.

### 3. 2-Hop Komşular

1-hop komşuların bir sonraki derece bağımlılıkları. Daha geniş etki alanını yakalar.

### 4. Topluluklar (Communities)

Leiden kümeleme algoritması ile otomatik olarak tespit edilen modül sınırlarıdır. Etkilenen dosyaların ait olduğu topluluklar belirlenir ve aynı topluluktaki diğer bileşenler de etki alanına dahil edilir.

### 5. God Node'lar

En çok bağımlılığa sahip merkezi bileşenlerdir. En yüksek etki yarıçapına (blast radius) sahip node'lar olarak tanımlanır. Bir god node etkileniyorsa, çok geniş bir kod alanı risk altındadır.

## Fallback Davranışı

Graphify sorgusu herhangi bir nedenle başarısız olursa (dosya yok, parse hatası vb.), pipeline hata vermez. Boş etki verisi ile devam eder:

```python
impact_data = graphify_client.query(seed_files) or {}
```

Bu graceful fallback, Graphify bağımlılığının zorunlu olmamasını sağlar. Graphify verisi yoksa bile pipeline çalışır.
