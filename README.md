# FreeRTOS Buton Yanıt Süresi Analizi (Yük Altında)

STM32F407G-DISC1 üzerinde FreeRTOS tabanlı, **yük altında buton → yanıt gecikmesini ölçen, kaynağını ayrıştıran** ve sonuçları bir **PC arayüzünden kontrol/izleme** imkânı sunan bir modül. Uzun vadede bir Edge AI projesinin temel ölçüm altyapısı olacak.

> "Butona bastım, yanıt ne zaman geldi? Gecikme nereden geldi?"

## Hedefler (özet)
1. Çalışan bir FreeRTOS sistemi kurmak.
2. Buton olayından yanıta kadar geçen süreyi aşamalara bölerek ölçmek.
3. Kontrollü yük senaryoları altında gecikmenin nasıl değiştiğini göstermek.
4. Gecikmenin kaynağını (donanım, ISR, zamanlayıcı, öncelik, kritik bölge, …) açıklamak.
5. Tüm senaryoları ve verileri PC arayüzünden yönetmek.

## Haftalar
| Hafta | Konu | Durum |
|---|---|---|
| [hafta-01](hafta-01/) | Yük altında buton yanıt süresi: 3 görev · UART arayüzü · ölçüm ve kanıt | ✅ Tamamlandı: 180 gerçek ölçüm, [rapor](hafta-01/analysis/report.md) |

## Temel Kararlar
| Konu | Seçim |
|---|---|
| Kart | STM32F407G-DISC1 (Cortex-M4F, 168 MHz) |
| Toolchain | STM32CubeIDE 1.10.1 araçları (gcc 10.3, make) + HAL (STM32CubeF4 V1.26.1) |
| RTOS | FreeRTOS V10.3.1 |
| PC ↔ Kart | USART2 (PA2/PA3) + harici USB-TTL, 115200 8N1, DMA TX |
| Ölçüm | Yalnızca iç ölçüm: TIM2 1 MHz zaman damgası (ilk taslaktaki DWT yerine; bkz. ADR-004) |
| PC arayüzü | Python + PySide6 + pyqtgraph |

Gerekçeler için: [hafta-01/docs/DECISIONS.md](hafta-01/docs/DECISIONS.md)

## Doküman Haritası (hafta-01)
| Doküman | İçerik |
|---|---|
| [gereksinim.md](hafta-01/docs/gereksinim.md) | Başlangıç (t₀), bitiş (t₄), deadline (20 ms), çalışma koşulları, senaryolar |
| [zaman-cizelgesi.md](hafta-01/docs/zaman-cizelgesi.md) | S0, S3, S5 zaman çizelgesi; R ve deadline payı (gerçek ölçümden) |
| [analiz.md](hafta-01/analysis/analiz.md) | Hipotezler, ölçüm planı, destekleyen/yanlışlayan veri |
| [report.md](hafta-01/analysis/report.md) | Gerçek kart sonuçları (ölçümden sonra) |
| [setup.md](hafta-01/docs/setup.md) | Bağlantılar, araç sürümleri, derleme, yükleme, ölçüm adımları |
| [code-notes.md](hafta-01/docs/code-notes.md) | ISR, görevler, UART tamamlanması, zaman hesapları |
| [protokol.md](hafta-01/docs/protokol.md) | MCU ↔ PC satır protokolü |
| [ROADMAP.md](hafta-01/docs/ROADMAP.md) | Durum ve öneriler |
| [ai-usage.md](hafta-01/docs/ai-usage.md) | Yapay zekâ kullanımı |

## Planlanan Klasör Yapısı
```
freeRTOS_Bootcamp/
├── README.md
├── docs/                 # Bu spec seti
├── firmware/             # STM32CubeIDE projesi
│   ├── Core/
│   ├── App/              # Uygulama katmanı (görevler, ölçüm, protokol)
│   └── Middlewares/      # FreeRTOS
├── pc_app/               # Python GUI
│   ├── src/
│   └── requirements.txt
└── results/              # Deney çıktıları (CSV/JSON), analiz defterleri
```

Her hafta bu planı kendi klasöründe uygular. `hafta-01` içinde ders teslim düzeni kullanılır:

| Plan | hafta-01 karşılığı |
|---|---|
| `docs/` | `hafta-01/docs/` (ilk taslak: `docs/arsiv-ilk-taslak/`) |
| `firmware/Core, App, Middlewares` | `hafta-01/firmware/` (aynı alt yapı + `Drivers/`, `Makefile`) |
| `pc_app/src`, `requirements.txt` | `hafta-01/interface/uart_monitor/`, `hafta-01/interface/requirements.txt` |
| `results/` | `hafta-01/measurements/` (ham CSV) + `hafta-01/analysis/` (rapor, grafik, betik) |

## Doküman Kuralları
- Önemli kararlar her haftanın `docs/DECISIONS.md` dosyasına ADR olarak eklenir.
- Tüm sonuçlar, tablolar ve grafikler gerçek kart ölçümünden üretilir; `measurements/` yalnızca gerçek kart verisi içerir.
