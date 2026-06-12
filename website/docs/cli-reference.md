---
sidebar_position: 10
title: "CLI Referansı"
---

# CLI Referansı

Tüm CLI komutları `python -m app.cli` üzerinden çalıştırılır.

## Komutlar

### `launch`

```bash
python -m app.cli launch TASK_KEY [-s source] [-p project_path]
```

Test zeka boru hattını (pipeline) başlatır.

| Parametre         | Açıklama                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `TASK_KEY`        | Jira görev anahtarı (ör. `PROJ-123`)                                    |
| `-s`, `--source`  | Veri kaynağı. Varsayılan: `jira`                                        |
| `-p`, `--project_path` | Proje kök dizini. Varsayılan: geçerli dizin                        |

**Davranış:**

1. **`_ensure_jira_raw`** — Eğer `jira-raw.json` dosyası mevcut değilse, otomatik olarak boş bir stub oluşturur. Pipeline bu dosyayı Jira'dan çekilen ham verilerle doldurur.
2. **`_ensure_web_open`** — Web sunucusunu `DETACHED_PROCESS` modunda başlatır (arka planda çalışır). Ardından varsayılan tarayıcıda web arayüzünü açar.
3. Boru hattını asenkron olarak çalıştırır ve ilk aşamadan itibaren tüm süreçleri başlatır.

**Örnek:**

```bash
python -m app.cli launch PROJ-123 -s jira -p C:/repos/ob-project
```

---

### `resume`

```bash
python -m app.cli resume TASK_KEY [-r response]
```

Kullanıcı kontrol noktasında (checkpoint) duraklatılmış boru hattını devam ettirir.

| Parametre         | Açıklama                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `TASK_KEY`        | Jira görev anahtarı                                                     |
| `-r`, `--response` | Kullanıcı yanıtı. Varsayılan: `approve`                               |

Pipeline, kullanıcı checkpoint'lerinden geçerken `resume` komutu ile onay veya red yanıtı gönderilir. Varsayılan yanıt `approve` olduğu için komuta ek parametre verilmezse süreç otomatik olarak onaylanır ve devam eder.

**Örnek:**

```bash
python -m app.cli resume PROJ-123
python -m app.cli resume PROJ-123 -r reject
```

---

### `poll`

```bash
python -m app.cli poll TASK_KEY
```

Belirtilen görevin mevcut boru hattı durumunu gösterir.

| Parametre   | Açıklama              |
| ----------- | --------------------- |
| `TASK_KEY`  | Jira görev anahtarı   |

Mevcut aşamayı, tamamlanma durumunu ve varsa hata bilgilerini görüntüler.

**Örnek:**

```bash
python -m app.cli poll PROJ-123
```

---

### `status`

```bash
python -m app.cli status
```

Tüm test görevlerini tablo biçiminde listeler.

Tablo şu sütunları içerir:

| Sütun       | Açıklama                          |
| ----------- | --------------------------------- |
| Task Key    | Jira görev anahtarı               |
| Phase       | Mevcut boru hattı aşaması         |
| Source      | Veri kaynağı                      |
| Updated     | Son güncelleme zamanı             |

**Örnek:**

```bash
python -m app.cli status
```

---

### `smoke`

```bash
python -m app.cli smoke
```

Sistem sağlık kontrolü (smoke test) yapar.

Aşağıdaki bileşenleri kontrol eder:

| Kontrol             | Açıklama                                                    |
| ------------------- | ----------------------------------------------------------- |
| Config loaded       | `app.yaml` başarıyla yüklendi                               |
| ob-core path        | `ob_core` yolu erişilebilir ve geçerli                     |
| graphify graph      | `graphify` graf dosyası erişilebilir                       |
| context path        | `context` dizini erişilebilir                               |
| outputs dir         | `outputs` çıktı dizini erişilebilir                        |

Her kontrol sonucu `OK` veya `FAIL` olarak raporlanır.

**Örnek:**

```bash
python -m app.cli smoke
```

---

## Dahili Davranışlar

### `_ensure_jira_raw`

`launch` komutu çalıştırıldığında, hedef dizinde `jira-raw.json` dosyası aranır. Dosya mevcut değilse, boş bir JSON stub olarak oluşturulur. Bu dosya, pipeline'ın Jira API'den çektiği ham görev verilerini saklamak için kullanılır. Stub yapısı şöyledir:

```json
{
  "key": "",
  "summary": "",
  "description": "",
  "status": "",
  "comments": []
}
```

### `_ensure_web_open`

`launch` komutu çalıştırıldığında, web sunucusunun zaten çalışıp çalışmadığı kontrol edilir. Çalışmıyorsa, sunucu `DETACHED_PROCESS` bayrağıyla ayrı bir süreç olarak başlatılır. Bu sayede CLI işlemi bittikten sonra bile web arayüzü aktif kalır. Sunucu başlatıldıktan sonra varsayılan tarayıcıda `http://localhost:<port>` adresi açılır.
