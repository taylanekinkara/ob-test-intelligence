---
sidebar_position: 2
title: "Hızlı Başlangıç"
---

# Hızlı Başlangıç

ob-test-intelligence'i kurmak ve ilk testinizi çalıştırmak için bu rehberi takip edin.

## Ön Koşullar

| Gereksinim | Minimum Sürüm |
|------------|---------------|
| Python | 3.14+ |
| Node.js | 20+ (web arayüzü için) |
| Git | Yüklü |

## 1. Repoyu Klonlayın

```bash
git clone <repo-url>
cd ob-test-intelligence
```

## 2. Sanal Ortam Oluşturun

```bash
python -m venv .venv
```

**Windows:**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

## 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

## 4. Ortam Değişkenlerini Yapılandırın

Proje kök dizininde `.env` dosyası oluşturun:

```env
# Jira bağlantı ayarları
OB_JIRA_SERVER=https://jira.sirket.com
OB_JIRA_EMAIL=kullanici@sirket.com
OB_JIRA_TOKEN=jira-api-token

# OpenAI ayarları
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1

# Proje yolları
OB_PROJECT_ROOT=C:\repos\proje-adi
OB_OUTPUT_DIR=outputs
```

### Zorunlu Değişkenler

| Değişken | Açıklama |
|----------|----------|
| `OB_JIRA_SERVER` | Jira sunucu adresi |
| `OB_JIRA_EMAIL` | Jira kullanıcı e-postası |
| `OB_JIRA_TOKEN` | Jira API token |
| `OPENAI_API_KEY` | OpenAI API anahtarı |
| `OPENAI_BASE_URL` | OpenAI uyumlu API base URL |

## 5. İlk Çalıştırma

Bir Jira/PDB görevi için test pipeline'ını başlatın:

```bash
python -m app.cli launch PDB-12345
```

Pipeline başladığında tarayıcı otomatik olarak **http://localhost:8081/test/PDB-12345** adresinde açılır.

## 6. Pipeline Süreci

Pipeline aşağıdaki aşamalardan geçer:

1. Görev bilgilerini Jira'dan çeker
2. Kodu analiz eder
3. Test değerlendirmesi (assessment) oluşturur
4. **`test_assess` kontrol noktasında duraklar**

Bu noktada web arayüzünde üretilen test öğelerini inceleyebilirsiniz.

## 7. Test Öğelerini İnceleyin

Web arayüzünde test detay sayfasında:

- Aşama ilerleme çubuğunu kontrol edin
- Üretilen test öğelerini ve senaryoları inceleyin
- Log çıktılarını takip edin

## 8. Devam Ettirin

Onayınızdan sonra pipeline'ı devam ettirin:

```bash
python -m app.cli resume PDB-12345
```

Pipeline kalan aşamaları tamamlayarak test raporunu üretir.

## 9. Raporu Görüntüleyin

Tamamlanan test raporu aşağıdaki konumda bulunur:

```
outputs/tests/PDB-12345/report.md
```

Rapor; test senaryolarını, değerlendirme sonuçlarını ve token kullanım istatistiklerini içerir.

## 10. Web Sunucusunu Manuel Başlatma

CLI dışında web sunucusunu bağımsız olarak başlatmak isterseniz:

```bash
python -m uvicorn app.web.app:app --host 0.0.0.0 --port 8081
```

Sunucu başladıktan sonra tarayıcınızda **http://localhost:8081** adresine giderek dashboard'a erişebilirsiniz.

## Sonraki Adımlar

- [Pipeline aşamaları](./pipeline-phases) hakkında detaylı bilgi edinin
- [Token takibi](./token-tracking.md) ile LLM kullanımını optimize edin
- [Web dashboard](./web-dashboard.md) özelliklerini keşfedin
