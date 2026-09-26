# 03 — Donanım Spesifikasyonu

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Bileşenler
| Bileşen | Açıklama |
|---|---|
| STM32F407G-DISC1 | STM32F407VGT6, Cortex-M4F, 1 MB Flash, 192 KB RAM (112+16+64 CCM) |
| USB-TTL dönüştürücü | 3.3 V lojik seviyeli (CP2102 / CH340 / FT232 vb.) |
| Kablolar | 3 adet dişi-dişi jumper (TX, RX, GND) |
| Mini-USB kablo | ST-LINK/V2 (programlama + besleme) |

> **Uyarı:** USB-TTL modülü mutlaka 3.3 V lojik seviyesinde olmalı veya 3.3 V moduna alınmalıdır. USB-TTL'in VCC pinini karta bağlamayın; kart ST-LINK USB'sinden beslenir.

## 2. Saat Yapılandırması
| Parametre | Değer |
|---|---|
| Kaynak | HSE 8 MHz (ST-LINK MCO'dan) |
| SYSCLK | 168 MHz (PLL: M=8, N=336, P=2, Q=7) |
| AHB / APB1 / APB2 | 168 / 42 / 84 MHz |
| Flash latency | 5 WS, ART accelerator (prefetch + I/D cache) açık |
| DWT CYCCNT | 168 MHz → 1 çevrim ≈ 5,952 ns, taşma ≈ 25,57 s |

> Flash cache/prefetch ayarları gecikmeyi etkiler; deney raporlarında sabit tutulmalı ve kaydedilmelidir.

## 3. Pin Haritası

### 3.1 Kullanılan Pinler
| Pin | Fonksiyon | Yön | Not |
|---|---|---|---|
| PA0 | B1 kullanıcı butonu → EXTI0 | Giriş | Aktif-yüksek, kart üzerinde pull-down + RC filtre (şematikten doğrulanacak) |
| PA2 | USART2_TX → USB-TTL RX | Çıkış | AF7 |
| PA3 | USART2_RX ← USB-TTL TX | Giriş | AF7 |
| GND | USB-TTL GND | — | Ortak toprak zorunlu |
| PD12 | LED4 yeşil — Heartbeat / sistem canlı | Çıkış | |
| PD13 | LED3 turuncu — Yük aktif göstergesi | Çıkış | |
| PD14 | LED5 kırmızı — Hata (assert, overflow, olay kaybı) | Çıkış | |
| PD15 | LED6 mavi — **Buton yanıtı** | Çıkış | Ölçülen yanıt aksiyonu |
| PE7–PE10 (öneri) | Test/debug GPIO (ISR girişi, görev başlangıcı, yanıt) | Çıkış | İleride harici doğrulama yapılırsa kullanılmak üzere ayrıldı |

### 3.2 Kaçınılması Gereken Pinler (kart üzerinde dolu)
| Pinler | Kullanan |
|---|---|
| PA5, PA6, PA7, PE3 | LIS3DSH ivmeölçer (SPI1) |
| PB6, PB9, PD4, PA4, PC7, PC10, PC12 | CS43L22 audio DAC (I2C1, I2S3) |
| PA9–PA12, PC0 | USB OTG FS |
| PA13, PA14, PB3 | SWD / SWO |
| PH0, PH1 | HSE |

## 4. Zamanlayıcı Tahsisi
| Timer | Kullanım |
|---|---|
| SysTick | FreeRTOS tick (configTICK_RATE_HZ = 1000, TBD) |
| TIM6 | HAL timebase (FreeRTOS ile SysTick çakışmasını önlemek için) |
| TIM7 | Periyodik kesme yükü üreteci (FR-021) |
| TIM2 (32-bit) | Yedek — gerekirse run-time stats sayacı |

## 5. Bağlantı Şeması
```
  STM32F407G-DISC1            USB-TTL (3.3 V)
  ────────────────            ───────────────
  PA2 (USART2_TX)  ─────────► RXD
  PA3 (USART2_RX)  ◄───────── TXD
  GND              ────────── GND
                              VCC  (bağlanmaz)
```
