# Hafta 01: Yük Altında Buton Yanıt Süresi Analizi

STM32F407G-DISC1 üzerinde FreeRTOS: **3 uygulama görevi · UART arayüzü · ölçüm ve kanıt.**

Butona basıldığında orta öncelikli `ButtonTask` "butona basıldı" yanıtını üretir. Telemetri hızı ve CPU yükü değiştirilerek yanıt süresi (R = t₄ − t₀) ölçülür. Gecikmenin **ne kadar**, **hangi koşulda** ve **hangi aşamada** değiştiği grafik ve ham veriyle açıklanır.

> ✅ **Gerçek kart ölçümleri tamamlandı:** S0–S5, 6 × 30 = 180 olay. Sonuçlar: [analysis/report.md](analysis/report.md)

## Sonuç özeti (gerçek ölçüm)
| Senaryo | Koşul | R ort. | R gözlenen maks. | Min pay | Deadline | Değişen aşama |
|---|---|---|---|---|---|---|
| S0 | Telemetri kapalı | 5,59 ms | 5,59 ms | +14,41 ms | 30/30 ✅ | — (R ≈ UART hat süresi) |
| S1 | 10 Hz | 5,74 ms | 10,11 ms | +9,89 ms | 30/30 ✅ | t₃−t₂ (FIFO'da TEL bekleme) |
| S2 | 50 Hz | 6,20 ms | 10,29 ms | +9,71 ms | 30/30 ✅ | t₃−t₂ |
| S3 | 100 Hz | 7,08 ms | 11,17 ms | +8,83 ms | 30/30 ✅ | t₃−t₂ (≤ 1 mesaj süresi) |
| S4 | 100 Hz + 2 ms CPU | 8,50 ms | 13,06 ms | +6,94 ms | 30/30 ✅ | t₁−t₀ (≤ 1,9 ms) + t₃−t₂ |
| S5 | 100 Hz + 5 ms CPU | 98,50 ms | 165,16 ms | −145,16 ms | **0/30 ❌** (18 geç, 12 kayıp) | t₃−t₂ her basışta +10 ms: UartTxTask CPU açlığı |

### İyileştirme: kaymayı en aza indirmek (gerçek kart, EXTI enjeksiyonu, 18 deney × 50 olay)
| En kötü R (ms) | S0 | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|---|
| **A** · görev standardı | 5,60 | 9,84 | 10,97 | 10,97 | 13,01 | **165,34** ❌ |
| **B** · öncelikli yanıt kuyruğu | 5,59 | 10,94 | 10,98 | 10,94 | 10,98 | 15,36 (35 TEL düştü) |
| **C** · B + öncelik Btn > Uart > Tel | 5,59 | 7,97 | 10,95 | 11,00 | 10,98 | **10,87** ✅ |

C ile her senaryoda en kötü yanıt ≈ 11 ms; buton ve telemetri kaybı yok. Kalan kayma, hatta o anda giden 64 baytlık mesajın süresidir; 115200 baud'da bunun altına inilemez. Ayrıntı: [report.md §8](analysis/report.md).

## Teslimler

| Teslim | Dosya |
|---|---|
| Gereksinim: başlangıç, bitiş, deadline, çalışma koşulları | [docs/gereksinim.md](docs/gereksinim.md) |
| Üç senaryonun zaman çizelgesi, R ve deadline payı (gerçek ölçümden) | [docs/zaman-cizelgesi.md](docs/zaman-cizelgesi.md) |
| Hipotez ve ölçüm planı: hangi veri destekler, hangisi yanlışlar | [analysis/analiz.md](analysis/analiz.md) |
| Sonuç raporu (ham veriye dayalı) | [analysis/report.md](analysis/report.md) |

## Sistem

```
 B1 ─► EXTI0 ISR (t0) ─buttonQ[8]─► ButtonTask (2)  (t1,t2) ─┐
                                                              ├─ txQ[16] FIFO ─► UartTxTask (1) ─DMA─► USART2 ─► PC
       TelemetryTask (3)  periyodik TEL + CPU işi ───────────┘                   (t3)      TC ISR (t4)
```

| Görev | Öncelik | Sorumluluk |
|---|---|---|
| TelemetryTask | Yüksek · 3 | Periyodik veri üretir, ortak TX kuyruğuna bırakır |
| ButtonTask | Orta · 2 | Buton olayını alır, yanıtı üretir, TX kuyruğuna bırakır |
| UartTxTask | Düşük · 1 | FIFO kuyruğunu tüketir; **UART'ın tek sahibi** |

## Kart, bağlantılar ve araçlar
- **Kart:** STM32F407G-DISC1, 168 MHz. **Buton:** kart üzerindeki mavi USER (B1, PA0); hem ölçülen buton hem deney kontrolü. **UART:** PA2 (TX) → USB-TTL RXD, GND–GND; 115200 8N1, 3,3 V. PC → kart hattı (PA3 ← TXD) isteğe bağlıdır. ST-LINK'in COM portu bu kartta PA2/PA3'e bağlı değildir.
- **Araçlar:** STM32CubeIDE 1.10.1 (gcc 10.3-2021.10, make), STM32CubeF4 V1.26.1, FreeRTOS V10.3.1, Python 3.11, PySide6 6.11.
- Ayrıntılar: [docs/setup.md](docs/setup.md).

## Hızlı başlangıç
```bash
# 1) Firmware (Git Bash; CubeIDE araç yollarını PATH'e ekleyin — docs/setup.md §3)
cd hafta-01/firmware && make -j8 && make flash

# 2) Arayüz
cd ../interface
py -3.11 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uart_monitor

# 3) Özet + grafikler: arayüzde "Analiz ve grafikler" sekmesi → ▶ Analizi çalıştır
#    (veya komut satırından)
cd .. && interface/.venv/Scripts/python analysis/scripts/analyze.py
```

## Senaryo seçimi ve ölçüm
Her senaryoda aynı sıra, mavi butonla: **kısa bas** = sonraki senaryo → **uzun bas** = START (5 s ısınma) → **30 basış** (aralarında ≥ 0,5 s, düzensiz) → 30. yanıt hattan çıkınca **otomatik STOP + DUMP** → arayüz CSV'yi kaydeder. Adım adım anlatım için [docs/setup.md §6](docs/setup.md#6-senaryo-seçimi-ve-ölçüm-adımları).

| ID | Telemetri | Ek CPU işi |
|---|---|---|
| S0 | Kapalı | — |
| S1 | 10 Hz | — |
| S2 | 50 Hz | — |
| S3 | 100 Hz | — |
| S4 | 100 Hz | ≈ 2 ms |
| S5 | 100 Hz | ≈ 5 ms |

## Timer ve FreeRTOS ayarları
TIM2 1 MHz 32 bit zaman damgası · SysTick 1 kHz · preemptive + time slicing · `configUSE_TIMERS = 0` · `MAX_SYSCALL` önceliği 5 (EXTI0 = 5, USART2/DMA = 6) · heap_4 24 KB · `-O2`. Tam tablo: [docs/setup.md §4](docs/setup.md#4-timer-ve-freertos-ayarları-rapora-yazılır).

## Ham veri, grafik, rapor

| | |
|---|---|
| Ham ölçümler | [measurements/](measurements/): `S0.csv … S5.csv`, `Sx_counters.csv`, `raw/`, `summary.csv` |
| Grafikler | [analysis/plots/](analysis/plots/), üreten kod [analysis/scripts/analyze.py](analysis/scripts/analyze.py) |
| Rapor | [analysis/report.md](analysis/report.md) (§8: A/B/C iyileştirme) |
| Varyant ölçümleri | [measurements/runs/](measurements/runs/), [variants_summary.csv](measurements/variants_summary.csv), [variants_tables.md](analysis/variants_tables.md) |

## Diğer dokümanlar
[code-notes.md](docs/code-notes.md) (ISR, görevler, UART tamamlanması, zaman hesapları) · [protokol.md](docs/protokol.md) · [DECISIONS.md](docs/DECISIONS.md) · [ROADMAP.md](docs/ROADMAP.md) (öneriler) · [ai-usage.md](docs/ai-usage.md)

## Klasör yapısı
```
hafta-01/
├── README.md
├── firmware/        Makefile · App/ (uygulama) · Core/ · Drivers/ · Middlewares/FreeRTOS
├── interface/       uart_monitor/ (PySide6) · tests/ · requirements.txt
├── measurements/    S0.csv … S5.csv · Sx_counters.csv · raw/ · summary.csv
├── analysis/        analiz.md · report.md · plots/ · scripts/
└── docs/            gereksinim.md · zaman-cizelgesi.* · setup.md · code-notes.md · protokol.md · ai-usage.md
```

## Teslim kontrol listesi
- [x] Firmware ve arayüz kaynakları çalıştırılabilir (kartta çalıştırıldı ve ölçüldü)
- [x] S0–S5 ham ölçümleri, kayıp sayaçları ve özet tablo depoda
- [x] Grafikler ve analiz raporu ham veriye dayanıyor
- [x] Kritik kod blokları açıklanmış; AI kullanımı belirtilmiş
- [ ] Depo erişimi, çalıştırma adımları ve teslim commit'i hazır
