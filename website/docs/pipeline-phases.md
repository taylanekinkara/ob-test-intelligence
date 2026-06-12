---
sidebar_position: 3
title: "Pipeline Fazları"
---

# Pipeline Fazları

ob-test-intelligence pipeline'ı 10 fazdan oluşur. Her faz belirli bir sorumluluğa sahiptir ve bir sonraki faza veri aktarır. İki fazda (**test_assess** ve **scenario_generate**) kullanıcı onayı beklenir.

## Genel Akış

```
ensure_ready → task_read → code_analyze → impact_analyze → test_assess ⏸️ → scenario_generate ⏸️ → env_prepare → test_execute → verify → report
```

---

## 1. ensure_ready

### Amaç

Pipeline çalışmadan önce sistemin sağlıklı olduğunu doğrular. Eksik bağımlılıklar uyarı olarak kaydedilir ancak pipeline'ı durdurmaz.

### Girdiler

- Sanal ortam (venv) yolu
- LLM servis URL'si
- Graphify graph.json yolu
- Context dizini yolu
- ob-core dizini yolu
- `jira-raw.json` dosya yolu

### Çıktılar

- **readiness_checks**: Her kontrol noktası için `ready` / `not_ready` durumu
- **warnings**: Eksik veya sorunlu bağımlılıkların listesi

### Kontroller

| Kontrol | Açıklama |
|---------|----------|
| venv | Python sanal ortamının varlığı |
| LLM health | LLM servisine health ping gönderimi |
| graph.json | Graphify bağımlılık grafiğinin varlığı |
| context path | Domain context dosyalarının bulunduğu dizin |
| ob-core path | ob-core kaynak kodunun bulunduğu dizin |
| jira-raw.json | Jira ham verisinin varlığı |

### Temel Mantık

1. Her kontrol noktası sırayla doğrulanır.
2. Başarısız kontroller `warnings` listesine eklenir.
3. Hiçbir uyarı pipeline'ı engellemez; tüm fazlar `warning` ile devam edebilir.

### Geri Dönüş Davranışı

Bir kontrol başarısız olursa ilgili faz kendi hata mesajını üretir. `ensure_ready` sadece uyarı üretir, istisna fırlatmaz.

---

## 2. task_read

### Amaç

Jira verisini okur, domain tespiti yapar, branch adını çıkarır ve LLM ile yapılandırılmış bir görev özeti oluşturur.

### Girdiler

- `jira-raw.json` (issue alanları, yorumlar, geliştirme bilgisi)

### Çıktılar

`task-summary.json`:

| Alan | Açıklama |
|------|----------|
| `title` | Görev başlığı |
| `description_summary` | Açıklamanın özeti |
| `domain` | Tespit edilen domain (ör: payment, bus, hotel) |
| `affected_verticals` | Etkilenen vertikaller |
| `what_changed` | Yapılan değişikliğin özeti |
| `expected_behavior` | Beklenen davranış |
| `acceptance_criteria` | Kabul kriterleri |
| `branch` | Branch adı |
| `risk_level` | Risk seviyesi |

### Kullanılan LLM Prompt'u

- **task_analyzer.md**

### Temel Mantık

1. `jira-raw.json` okunur; issue alanları, yorumlar ve `dev_info` çıkarılır.
2. Başlık ve açıklamadaki anahtar kelimelerden domain tespiti yapılır (ör: "ödeme", "payment" → payment domain).
3. `dev_info` içinden branch adı çıkarılır.
4. `ContextLoader` ile domain'e özel context yüklenir.
5. Tüm veriler LLM'e gönderilir; `task_analyzer.md` prompt'u ile yapılandırılmış çıktı üretilir.

### Geri Dönüş Davranışı

- Branch bulunamazsa `task-summary.branch` boş bırakılır; `code_analyze` fazı uyarı verir.
- Domain tespit edilemezse `generic` olarak işaretlenir.

---

## 3. code_analyze

### Amaç

Branch üzerindeki değişen dosyaları analiz eder, katman ve domain sınıflandırması yapar, mimari context ile zenginleştirilmiş bir kod analizi üretir.

### Girdiler

- `task-summary.json` (branch adı)

### Çıktılar

`code-analysis.json`:

| Alan | Açıklama |
|------|----------|
| `branch` | Analiz edilen branch |
| `files_changed` | Değişen dosya listesi (her biri için `layer`, `domain`, `change_type`) |
| `layers_affected` | Etkilenen katmanlar |
| `domains_affected` | Etkilenen domainler |
| `endpoints_affected` | Etkilenen API endpoint'leri |
| `llm_summary` | LLM üretimi özet |

### Kullanılan LLM Prompt'u

- **code_analyzer.md**

### Temel Mantık

1. `task-summary.json`'dan branch adı alınır.
2. `git diff_files` ile değişen dosya listesi alınır.
3. `git diff_content` ile her dosyanın diff içeriği alınır (maksimum 50.000 karakter sınırı).
4. Dosyalar katmanlarına göre sınıflandırılır:
   - `controller` — REST controller dosyaları
   - `service` — İş mantığı katmanı
   - `entity` — Veri modeli / entity dosyaları
   - `view` — Sunum katmanı dosyaları
5. Dosyalar domainlerine göre gruplandırılır.
6. Mimari context yüklenir.
7. Tüm veriler LLM'e gönderilir; `code_analyzer.md` prompt'u ile analiz yapılır.

### Geri Dönüş Davranışı

- Diff içeriği 50K karakteri aşarsa kesilir; ilk 50K karakter kullanılır.
- Branch'te değişiklik yoksa boş dosya listesi döner.

---

## 4. impact_analyze

### Amaç

Değişen dosyaların kod tabanındaki yayılım etkisini Graphify bağımlılık grafiği ile analiz eder. Risk değerlendirmesi yapar.

### Girdiler

- `code-analysis.json` (seed dosyalar)
- Graphify graph.json (bağımlılık grafiği)

### Çıktılar

`impact-analysis.json`:

| Alan | Açıklama |
|------|----------|
| `seed_files` | Analiz başlangıç dosyaları |
| `one_hop` | Doğrudan bağımlı dosyalar |
| `two_hop` | Dolaylı bağımlı dosyalar (2. derece) |
| `communities_affected` | Etkilenen Graphify toplulukları |
| `god_nodes_affected` | Etkilenen "god node" dosyaları |
| `overall_risk` | Genel risk seviyesi (`high` / `medium` / `low`) |
| `regression_areas` | Regresyon riski taşıyan alanlar |
| `risk_factors` | Risk faktörlerinin listesi |

### Kullanılan LLM Prompt'u

- **impact_assessor.md**

### Temel Mantık

1. `code-analysis.json`'dan seed dosyalar alınır.
2. Graphify sorgulanır:
   - **1-hop**: Seed dosyaların doğrudan bağımlılıkları
   - **2-hop**: Dolaylı bağımlılıklar
   - **Communities**: Etkilenen topluluklar
   - **God nodes**: Yüksek bağlantılı kritik dosyalar
3. Statik risk değerlendirmesi uygulanır:

   | Koşul | Risk |
   |-------|------|
   | Payment domain | `high` |
   | API controller veya service katmanı | `medium` |
   | Diğer tüm durumlar | `low` |

4. LLM'e gönderilir; `impact_assessor.md` prompt'u ile regresyon alanları ve risk faktörleri belirlenir.

### Geri Dönüş Davranışı

- Graphify grafiği yoksa sadece statik risk değerlendirmesi yapılır; Graphify verisi olmadan uyarı üretilir.

---

## 5. test_assess

### Amaç

Önceki fazların çıktılarını birleştirerek hangi testlerin yazılması gerektiğini belirler. Hangi testlerin **yapılacağını** ve hangilerinin **atlanacağını** kararlaştırır.

:::info Kullanıcı Onayı Gerekli
Bu faz tamamlandıktan sonra pipeline durur. Kullanıcı `test-assessment.json` çıktısını inceleyip onaylamalıdır.
:::

### Girdiler

- `task-summary.json`
- `code-analysis.json`
- `impact-analysis.json`

### Çıktılar

`test-assessment.json`:

| Alan | Açıklama |
|------|----------|
| `needs_testing` | Test gerekip gerekmediği (`true` / `false`) |
| `test_items` | Test öğeleri listesi |
| `skip_items` | Atlanan öğeler ve nedenleri |
| `environment` | Önerilen test ortamı |

Her `test_item`:

| Alan | Açıklama |
|------|----------|
| `id` | Benzersiz tanımlayıcı |
| `target` | Hedef dosya veya endpoint |
| `description` | Test açıklaması |
| `test_type` | Test türü (ör: `integration`, `functional`, `security`) |
| `priority` | Öncelik (`p0`, `p1`, `p2`, `p3`) |
| `domain` | İlgili domain |

### Kullanılan LLM Prompt'u

- **test_assessor.md**

### Temel Mantık

1. Üç önceki fazın çıktıları birleştirilir.
2. LLM, `test_assessor.md` prompt'u ile test öğeleri ve atlanacak öğeler üretir.
3. **Sabit kurallar** (override edilemez):
   - **Payment domain** → her zaman test üretilir, öncelik **p0** veya **p1**.
   - **API controller / service katmanı** → her zaman test üretilir, öncelik **p0** veya **p1**.
4. **Anti-pattern kuralları** uygulanır:
   - Mirror endpoint tekrarı engellenir (aynı endpoint için birden fazla özdeş test yazılmaz).
   - Varyasyon patlaması önlenir (gereksiz parametre kombinasyonları üretilmez).
   - Çakışan güvenlik denetimleri birleştirilir.

### Geri Dönüş Davranışı

- LLM çıktısında sabit kurallara aykırı öğe varsa (ör: payment domain için test yok), sistem otomatik olarak test öğesi ekler.

---

## 6. scenario_generate

### Amaç

Her test öğesi için somut test senaryoları üretir. Her senaryo adımlar, doğrulamalar ve beklenen durum kodları içerir.

:::info Kullanıcı Onayı Gerekli
Bu faz tamamlandıktan sonra pipeline durur. Kullanıcı `test-scenarios.json` çıktısını inceleyip onaylamalıdır.
:::

### Girdiler

- `test-assessment.json` (test_items listesi)

### Çıktılar

`test-scenarios.json`:

| Alan | Açıklama |
|------|----------|
| `scenarios` | Senaryo listesi |

Her senaryo:

| Alan | Açıklama |
|------|----------|
| `id` | Benzersiz senaryo tanımlayıcısı |
| `test_item_id` | İlişkili test öğesi |
| `name` | Senaryo adı |
| `type` | Senaryo türü (`happy_path`, `edge_case`, `error_case`) |
| `steps` | HTTP istek adımları |
| `assertions` | Beklenen doğrulama kuralları |
| `expected_status_code` | Beklenen HTTP durum kodu |

### Kullanılan LLM Prompt'u

- **scenario_generator.md**

### Temel Mantık

1. `test-assessment.json`'daki her `test_item` sırayla işlenir.
2. Her öğe için LLM'e `scenario_generator.md` prompt'u ile senaryo ürettirilir.
3. Minimum senaryo türleri garanti edilir:
   - **happy_path**: Başarılı akış senaryosu
   - **edge_case**: Sınır koşul senaryosu
   - **error_case**: Hata akış senaryosu
4. Test öğeleri arasında **2 saniyelik** throttle uygulanır (rate limiting).

### Geri Dönüş Davranışı

- LLM belirli bir senaryo türünü üretmezse, sistem minimum türleri otomatik olarak ekler.
- Throttle sayesinde API rate limit aşılmaz.

---

## 7. env_prepare

### Amaç

Testlerin çalıştırılacağı ortamın hazır olduğunu doğrular. Docker ve API erişilebilirliğini kontrol eder.

### Girdiler

- Yapılandırma dosyasındaki Docker ve API ayarları

### Çıktılar

`env-status.json`:

| Alan | Açıklama |
|------|----------|
| Docker durumu | Çalışıyor / çalışmıyor |
| API erişilebilirliği | Ulaşılabilir / ulaşılamaz |
| Ortam detayları | Tespit edilen ortam bilgileri |

### Temel Mantık

1. Docker servisinin çalışıp çalışmadığı kontrol edilir.
2. Hedef API'nin erişilebilir olduğu doğrulanır (health check).
3. Ortam durumu kayıt altına alınır.

### Geri Dönüş Davranışı

- Docker çalışmıyorsa `env-status.json`'da `docker_ready: false` olarak işaretlenir.
- API erişilemezse `api_ready: false` olarak işaretlenir.
- `test_execute` fazı bu durumu değerlendirerek senaryoları atlayabilir.

---

## 8. test_execute

### Amaç

Üretilen test senaryolarını yerel API'ye karşı çalıştırır. Her senaryonun sonucunu (başarılı / başarısız) kaydeder.

### Girdiler

- `test-scenarios.json`
- `env-status.json`

### Çıktılar

`test-results.json`:

| Alan | Açıklama |
|------|----------|
| `execution_time` | Toplam çalıştırma süresi |
| `total_scenarios` | Toplam senaryo sayısı |
| `passed` | Başarılı senaryo sayısı |
| `failed` | Başarısız senaryo sayısı |
| `skipped` | Atlanan senaryo sayısı |
| `results` | Her senaryonun detayı |

Her `result`:

| Alan | Açıklama |
|------|----------|
| `scenario_id` | Senaryo tanımlayıcısı |
| `passed` | Başarılı / başarısız |
| `status_code` | Alınan HTTP durum kodu |
| `assertions` | Assertion sonuçları |
| `duration_ms` | Senaryo çalıştırma süresi (ms) |

### Temel Mantık

1. `env-status.json` kontrol edilir; ortam hazır değilse uygun senaryolar `skipped` olarak işaretlenir.
2. Her senaryo sırayla çalıştırılır:
   - `steps` içindeki HTTP istekleri gönderilir.
   - Yanıtlar `assertions` ile karşılaştırılır.
   - Beklenen `status_code` ile alınan kod eşleştirilir.
3. Her senaryo için `passed` / `failed` kararı kaydedilir.
4. Toplam istatistikler hesaplanır.

### Geri Dönüş Davranışı

- API yanıt vermezse senaryo `skipped` olarak işaretlenir.
- Assertion hatasında `passed: false` kaydedilir; pipeline devam eder.

---

## 9. verify

### Amaç

Test sonuçlarını analiz eder, kapsam yüzdesini hesaplar ve yanlış pozitif / yanlış negatif tespiti yapar.

### Girdiler

- `test-results.json`
- `test-scenarios.json`
- `test-assessment.json`
- `impact-analysis.json`

### Çıktılar

`verification-report.json`:

| Alan | Açıklama |
|------|----------|
| `overall_verdict` | Genel değerlendirme (`pass` / `fail` / `partial`) |
| `coverage_percentage` | Test kapsama yüzdesi |
| `test_quality` | Test kalitesi değerlendirmesi |
| `findings` | Tespit edilen bulgular |
| `false_positives` | Yanlış pozitif senaryolar |
| `false_negatives` | Yanlış negatif senaryolar |

### Temel Mantık

1. Test sonuçları senaryolar ve etki analizi ile çapraz kontrol edilir.
2. Kapsama yüzdesi hesaplanır: etkilenen dosya / endpoint sayısına göre kapsanan alan oranı.
3. Yanlış pozitifler tespit edilir: başarılı olan ancak aslında test edilen davranışı kapsamayan senaryolar.
4. Yanlış negatifler tespit edilir: başarısız olan ancak testin kendisinde hata olan senaryolar.
5. Genel değerlendirme üretilir.

### Geri Dönüş Davranışı

- Sonuçlar yetersizse `overall_verdict: partial` olarak işaretlenir ve raporda öneriler sunulur.

---

## 10. report

### Amaç

Tüm pipeline sonuçlarını okunabilir bir Markdown raporu olarak sunar. Rapor; özet tablo, değişen dosyalar, etki analizi, test senaryoları, bulgular ve ortam bilgilerini içerir.

### Girdiler

- Tüm önceki faz çıktıları

### Çıktılar

- **report.md**: İnsan tarafından okunabilir Markdown rapor
- **report-meta.json**: Rapor üst verisi (oluşturulma tarihi, faz süreleri, token kullanımı)

### Rapor İçeriği

| Bölüm | Açıklama |
|-------|----------|
| Özet tablo | Toplam senaryo, geçen, kalan, kapsam yüzdesi |
| Değişen dosyalar | Katman ve domain sınıflandırmasıyla |
| Etki analizi | Risk seviyesi, etkilenen alanlar |
| Test senaryoları | Her senaryo adı, türü, sonucu |
| Bulgular | `verify` fazının tespitleri |
| Ortam bilgisi | Docker, API durumu |
| Token kullanım tablosu | Her fazda harcanan token sayısı |

### Temel Mantık

1. Tüm faz çıktıları toplanır.
2. Markdown rapor şu yapıda oluşturulur:
   - Başlık ve meta bilgiler
   - Özet tablo
   - Detaylı bölümler (her faz için)
   - Token kullanım özeti
3. Rapor dosyası ve meta verisi ayrı ayrı kaydedilir.

### Geri Dönüş Davranışı

- Bir faz çıktısı eksikse ilgili bölüm "Veri mevcut değil" olarak işaretlenir; rapor yine de oluşturulur.
