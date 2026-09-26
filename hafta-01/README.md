# Hafta 01: Yük Altında Buton Yanıt Süresi Analizi

STM32F407G-DISC1 üzerinde FreeRTOS: **3 uygulama görevi · UART arayüzü · ölçüm ve kanıt.**

Butona basıldığında orta öncelikli `ButtonTask` "butona basıldı" yanıtını üretir. Telemetri hızı ve CPU yükü değiştirilerek yanıt süresi (R = t₄ − t₀) ölçülür. Gecikmenin **ne kadar**, **hangi koşulda** ve **hangi aşamada** değiştiği grafik ve ham veriyle açıklanır.

> 🟡 **Ölçüm durumu:** Firmware, arayüz ve analiz hattı hazır. **Gerçek kart ölçümleri (S0–S5) henüz eklenmedi.** Zaman çizelgesindeki sayılar model tahminidir, ölçüm değildir.

## Teslimler

| Teslim | Dosya |
|---|---|
| Gereksinim: başlangıç, bitiş, deadline, çalışma koşulları | [docs/gereksinim.md](docs/gereksinim.md) |
| Üç senaryonun zaman çizelgesi, R ve deadline payı | [docs/zaman-cizelgesi.md](docs/zaman-cizelgesi.md) · [png](docs/zaman-cizelgesi.png) · [svg](docs/zaman-cizelgesi.svg) |
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
- **Kart:** STM32F407G-DISC1, 168 MHz. **UART:** PA2 (TX) → USB-TTL RXD, PA3 (RX) ← TXD, GND–GND; 115200 8N1, 3,3 V.
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

# 3) S0..S5 ölçümlerinden sonra özet + grafikler
cd .. && interface/.venv/Scripts/python analysis/scripts/analyze.py
```

## Senaryo seçimi ve ölçüm
Her senaryoda aynı sıra: **SCN** → **START** (5 s ısınma) → **≥ 30 basış** (aralarında ≥ 0,5 s, düzensiz) → **STOP → DUMP** → CSV. Adım adım anlatım için [docs/setup.md §6](docs/setup.md#6-senaryo-seçimi-ve-ölçüm-adımları).

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
| Rapor | [analysis/report.md](analysis/report.md) |
| Model (tahmin) | [analysis/model/](analysis/model/) |

## Diğer dokümanlar
[code-notes.md](docs/code-notes.md) (ISR, görevler, UART tamamlanması, zaman hesapları) · [protokol.md](docs/protokol.md) · [DECISIONS.md](docs/DECISIONS.md) · [ROADMAP.md](docs/ROADMAP.md) (öneriler) · [ai-usage.md](docs/ai-usage.md)

## Klasör yapısı
```
hafta-01/
├── README.md
├── firmware/        Makefile · App/ (uygulama) · Core/ · Drivers/ · Middlewares/FreeRTOS
├── interface/       uart_monitor/ (PySide6) · tests/ · requirements.txt
├── measurements/    S0.csv … S5.csv · Sx_counters.csv · raw/ · summary.csv
├── analysis/        analiz.md · report.md · plots/ · scripts/ · model/
└── docs/            gereksinim.md · zaman-cizelgesi.* · setup.md · code-notes.md · protokol.md · ai-usage.md
```

## Teslim kontrol listesi
- [x] Firmware ve arayüz kaynakları çalıştırılabilir (derleme ✔, birim testleri ✔; **kartta doğrulama bekliyor**)
- [ ] S0–S5 ham ölçümleri, kayıp sayaçları ve özet tablo depoda
- [ ] Grafikler ve analiz raporu ham veriye dayanıyor
- [x] Kritik kod blokları açıklanmış; AI kullanımı belirtilmiş
- [ ] Depo erişimi, çalıştırma adımları ve teslim commit'i hazır
- [ ] Videoda çalışan sistem ve senaryoların farkı gösterilmiş
