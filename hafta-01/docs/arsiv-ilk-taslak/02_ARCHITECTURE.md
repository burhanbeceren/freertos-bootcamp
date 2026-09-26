# 02 — Sistem Mimarisi

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Üst Seviye Blok Diyagramı
```
┌──────────────────────────── STM32F407G-DISC1 ────────────────────────────┐
│                                                                          │
│  B1 (PA0) ──► EXTI0 ISR ──notify──► ResponseTask ──► LED / Test GPIO     │
│                  │ t0                 │ t1 … tN                          │
│                  └──────────┬─────────┘                                  │
│                             ▼                                            │
│                     Measurement Module (DWT CYCCNT)                      │
│                             │  olay kaydı (ring buffer)                  │
│                             ▼                                            │
│   LoadManager ──► CPU yük görevleri / TIM kesme yükü / kritik bölge      │
│        ▲                                                                 │
│        │ parametreler                                                    │
│   CommandTask ◄── RX (USART2 IRQ/DMA) ◄────────────┐                     │
│   TelemetryTask ──► TX (USART2 DMA) ───────────────┼──┐                  │
│   MonitorTask (CPU yükü, stack, heap)              │  │                  │
└────────────────────────────────────────────────────┼──┼──────────────────┘
                                                     │  │  UART (3.3 V TTL)
                                               ┌─────┴──▼─────┐
                                               │  USB-TTL     │
                                               └──────┬───────┘
                                                      │ USB (COMx)
┌─────────────────────────── PC (Windows 11) ─────────▼────────────────────┐
│  SerialLink ─► ProtocolCodec ─► SessionStore ─► GUI (PySide6+pyqtgraph)  │
│                                     │                                    │
│                                     └─► CSV / JSON dışa aktarma          │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. Gecikme Zinciri (Kavramsal Model)
Gecikmenin kaynağını açıklamak için uçtan uca süre, ardışık aşamalara ayrılır. Kesin damga noktaları [05_MEASUREMENT_SPEC](05_MEASUREMENT_SPEC.md) içinde tanımlanacaktır.

```
 Fiziksel basış
   │  [A] Mekanik + RC filtre + giriş senkronizasyonu      ← iç ölçümle görülmez
   ▼
 EXTI bayrağı set
   │  [B] NVIC kesme girişi (stacking, flash wait state),  ← iç ölçümle görülmez
   │      daha yüksek öncelikli ISR / kesme kapalı bölge
   ▼
 ISR ilk komut ─────────────── t0
   │  [C] ISR gövdesi + FromISR çağrısı
   ▼
 portYIELD_FROM_ISR / PendSV
   │  [D] Zamanlayıcı gecikmesi: bağlam değişimi,
   │      daha yüksek/eş öncelikli görevler, scheduler askıda
   ▼
 ResponseTask çalışmaya başlar ─ t1
   │  [E] Uygulama işleme süresi
   ▼
 Yanıt GPIO set ─────────────── t2
```

Her yük türünün hangi aşamayı etkilemesi beklendiği (hipotez tablosu):

| Yük türü | Beklenen etkilenen aşama |
|---|---|
| Yüksek öncelikli CPU görevi | [D] |
| Eş öncelikli CPU görevi (time slicing) | [D] (tick periyoduna kadar) |
| Düşük öncelikli CPU görevi | Etki beklenmez (preemption) |
| Yüksek öncelikli periyodik kesme | [B], [C], [D] |
| `taskENTER_CRITICAL` / kesmeler kapalı | [B] |
| `vTaskSuspendAll` | [D] |
| Yoğun UART telemetri (DMA/IRQ) | [B], [D] |

> Deneylerin amacı bu hipotezleri doğrulamak veya çürütmektir.

## 3. Katmanlar

### 3.1 Firmware
| Katman | İçerik |
|---|---|
| HAL / CubeMX üretimi | Saat, GPIO, EXTI, USART2, TIM, NVIC — `firmware/Core` |
| RTOS | FreeRTOS kernel + FreeRTOSConfig.h |
| Platform soyutlama (BSP) | `bsp_gpio`, `bsp_uart`, `bsp_timer`, `bsp_dwt` |
| Uygulama (App) | `meas` (ölçüm), `load` (yük), `proto` (protokol), `tasks` (görevler), `config` (parametre deposu) |

### 3.2 PC Uygulaması
| Katman | İçerik |
|---|---|
| `link` | Seri port (pyserial), okuma iş parçacığı |
| `protocol` | Çerçeve kodlama/çözme, komut API'si |
| `model` | Olay, oturum, senaryo veri modelleri, istatistik |
| `ui` | PySide6 pencereleri, pyqtgraph grafikleri |
| `storage` | CSV/JSON kaydet/yükle |

## 4. Tasarım İlkeleri
1. **Ölçüm yolu kutsaldır:** ISR ve ResponseTask içinde yalnızca damga alma ve minimum iş; formatlama/gönderme başka görevde.
2. **Veri üretimi ile tüketimi ayrık:** Olaylar kilitsiz/ISR-güvenli ring buffer'a yazılır, TelemetryTask okur.
3. **Parametreler tek yerde:** Tüm çalışma anı ayarları `config` modülünde; PC yalnızca bunu değiştirir.
4. **Statik tahsis:** Görevler, kuyruklar, tamponlar statik veya başlangıçta ayrılır.
5. **Genişletilebilirlik:** Yük üreteçleri ortak bir arayüz (`start/stop/set_param`) uygular; Edge AI çıkarım görevi ileride bu arayüzle yeni bir yük olarak eklenir.
