# Analiz: Hipotez ve Ölçüm Planı

Bu doküman, görevin istediği "bir hipotez ve ölçüm planı" bölümüdür. Hipotezler ölçümden önce basit hesaplarla yazıldı. **Kararı gerçek kart ölçümleri verir.** Sonuçlar ve kararlar [report.md](report.md) içindedir.

## 1. Soru
"100 Hz daha yavaş" demek yeterli değil. Gecikme **ne kadar**, **hangi koşulda**, **hangi aşamada** (t₁−t₀, t₂−t₁, t₃−t₂, t₄−t₃) ve **neden** değişiyor?

## 2. Hesaba dayalı başlangıç noktaları
| Büyüklük | Değer |
|---|---|
| Bir mesajın hat süresi L = 64 × 10 / 115200 | 5,556 ms |
| Telemetri hat kullanımı U = L × f | 10 Hz: %5,6 · 50 Hz: %27,8 · 100 Hz: %55,6 |
| Ek CPU talebi C × f | S4: %20 · S5: %50 |

## 3. Hipotezler ve yanlışlama ölçütleri

### H0: UART aşaması (t₄−t₃) yükten bağımsızdır
TC kesmesi görevlerden önceliklidir; DMA, CPU'dan bağımsız çalışır.
- **Destekler:** Her senaryoda t₄−t₃ ≈ 5,56–5,6 ms ve yayılımı < 0,05 ms.
- **Yanlışlar:** t₄−t₃ yükle birlikte büyüyor.

### H1: Telemetri frekansı yalnızca t₃−t₂'yi uzatır (S0 → S3)
Yanıt, FIFO'da o an hatta olan TEL mesajının bitmesini bekler.
- **Destekler:**
  - t₃−t₂ ortalaması frekansla artar.
  - t₃−t₂ en fazla ≈ bir mesaj süresi (≈ 5,6 ms) olur.
  - t₁−t₀ ve t₂−t₁ değişmez.
  - `R_vs_phase` grafiğinde TEL'den hemen sonra yapılan basışlarda R daha büyüktür.
- **Yanlışlar:**
  - t₁−t₀ frekansla artıyor.
  - t₃−t₂, 2L'yi aşıyor.
  - R ile faz arasında ilişki yok.

### H2: 2 ms CPU işi t₁−t₀'ı uzatır, deadline korunur (S3 → S4)
TelemetryTask (öncelik 3) çalışırken ButtonTask (2) bekler.
- **Destekler:**
  - İş sırasında gelen basışlarda t₁−t₀ 2 ms'e kadar çıkar.
  - R, event_id ile birlikte artmaz.
  - `tx_drop` = 0.
  - `work_*_us` ≈ 2000.
- **Yanlışlar:**
  - t₁−t₀ > ~2,1 ms.
  - R olaydan olaya birikerek artıyor.

### H3: 5 ms CPU işinde darboğaz UartTxTask'ın CPU'ya erişimidir, hat değil (S4 → S5)
C + L = 5 + 5,56 > 10 ms. Bu yüzden bir TEL'in gönderimi, TelemetryTask'ın bir sonraki işinin içinde biter. En düşük öncelikli UartTxTask ancak iş bittikten sonra yeni mesaj başlatabilir. Hipotez: yanıt kuyrukta birikir.
- **Destekler:**
  - t₃−t₂ büyür (≫ 5,6 ms).
  - R, event_id ile artar (birikme).
  - `tx_drop` / `tel_tx_drop` > 0 olabilir.
  - Hat kullanımı %55,6 olmasına rağmen deadline kaçırılır.
- **Yanlışlar:**
  - t₃−t₂ ≤ ~5,6 ms kalıyor.
  - R, olaylar boyunca sabit kalıyor.
- **Uyarı:** `work_min_us` < ~4400 ise koşul (C + L > T) oluşmamıştır; S5 bu hipotezi test etmez.

## 4. Ölçüm planı
| Veri | Kaynak | Dosya |
|---|---|---|
| Olay başına t₀…t₄ + durum | MCU RAM kaydı → DUMP | `measurements/Sx.csv` |
| Kayıp/hata sayaçları, gerçek periyot, gerçek CPU işi | MCU `CNT` satırları | `measurements/Sx_counters.csv` |
| TEL üretim anları (MCU saati) | Ham UART dökümü | `measurements/raw/Sx_session.log` |

- Her senaryoda ≥ 30 basış yapılır; basışlar arasında ≥ 0,5 s olur ve zamanlama düzensizdir.
- Her senaryoda doğrulanır: `tel_period_*`, `work_*`, `log_overflow` = 0.

**Grafikler** (hepsi `analyze.py` ile ham CSV'den):
1. `R_vs_event.png`: olay → R, 20 ms çizgisi, kayıplar.
2. `stages_stacked.png`: senaryo → aşama ortalamaları.
3. `stages_box.png`: aşama dağılımları.
4. `R_vs_phase.png`: R ve telemetri fazı.
5. `docs/zaman-cizelgesi.png`: S0/S3/S5'ten gerçek olayların aşama çizelgesi.

## 5. Ölçüm sınırları
- t₀ fiziksel basma anı değildir; buton mekaniği ve RC filtre ölçülmez.
- t₄, TC kesmesinin **gözlendiği** andır; birkaç µs'lik kesme gecikmesi dahildir.
- n ≈ 30 ile gözlenen maksimum, kanıtlanmış worst-case değildir.
