# 04 — Firmware Spesifikasyonu

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Genel
- Ortam: STM32CubeIDE, CubeMX ile üretilen HAL projesi, FreeRTOS middleware.
- Uygulama kodunda **yerel FreeRTOS API** kullanılır (ör. `xTaskNotifyFromISR`); CMSIS-RTOS v2 sarmalayıcıları yalnızca CubeMX'in ürettiği başlangıç kodunda kalır (bkz. ADR-005).
- Uygulama kodu `firmware/App/` altında; CubeMX üretimi dosyalara yalnızca `USER CODE` blokları içinden çağrı eklenir.

## 2. Görev Tablosu (öneri)
Öncelik: yüksek sayı = yüksek öncelik (`configMAX_PRIORITIES = 8`, TBD).

| Görev | Öncelik | Stack (word) | Periyot / Tetik | Sorumluluk |
|---|---|---|---|---|
| ResponseTask | 6 (ayarlanabilir) | 256 | EXTI bildirimi | Damga al, yanıt GPIO set, olay kaydı yaz |
| CommandTask | 4 | 512 | RX çerçevesi | Komut çözme, parametre güncelleme, ACK |
| LoadTask_H | 5 (ayarlanabilir) | 256 | Parametreye bağlı | CPU yükü (ResponseTask'tan yüksek/eş denemesi için) |
| LoadTask_M | 3 (ayarlanabilir) | 256 | Parametreye bağlı | CPU yükü |
| LoadTask_L | 1 (ayarlanabilir) | 256 | Parametreye bağlı | CPU yükü |
| TelemetryTask | 2 | 512 | Olay kuyruğu / periyodik | Olay + durum kayıtlarını çerçeveleyip DMA ile gönder |
| MonitorTask | 2 | 256 | 500 ms | CPU yükü, stack HWM, heap, heartbeat LED |
| Idle | 0 | — | — | Idle hook: CPU yükü sayacı (TBD-09) |

> Görev öncelikleri çalışma anında `vTaskPrioritySet` ile PC'den değiştirilebilir (FR-024).

## 3. Kesme Yapılandırması
`configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY = 5` (öneri). Bu değerden **sayısal olarak küçük** (daha acil) öncelikli ISR'ler FreeRTOS API'si çağıramaz.

| Kesme | NVIC önceliği | FreeRTOS API? | Not |
|---|---|---|---|
| EXTI0 (buton) | 5 (ayarlanabilir) | Evet | `xTaskNotifyFromISR` + `portYIELD_FROM_ISR` |
| TIM7 (yük) | 5–15 veya <5 (ayarlanabilir) | Hayır | Sadece meşgul döngü; <5 seçilirse API çağrısı yasak |
| USART2 / DMA | 6 | Evet | RX çerçeve bildirimi, TX tamamlandı |
| TIM6 (HAL tick) | 15 | — | |
| SysTick / PendSV | 15 | — | FreeRTOS tarafından yönetilir |

`NVIC_PriorityGroup_4` (4 bit preemption, 0 bit sub-priority) kullanılmalıdır.

## 4. Modüller

### 4.1 `bsp_dwt` — Zaman Kaynağı
- `dwt_init()`: `CoreDebug->DEMCR |= TRCENA`, `DWT->CYCCNT = 0`, `DWT->CTRL |= CYCCNTENA`.
- `dwt_now()`: `static inline`, tek `LDR` ile CYCCNT okuması.
- Farklar `uint32_t` işaretsiz çıkarma ile hesaplanır (NFR-003).

### 4.2 `meas` — Ölçüm Modülü
- Olay yapısı, damga noktaları ve hesaplamalar: **[05_MEASUREMENT_SPEC](05_MEASUREMENT_SPEC.md)** (detaylandırılacak).
- Olaylar tek üretici / tek tüketici **kilitsiz ring buffer** ile TelemetryTask'a aktarılır. Buffer dolarsa olay düşürülür ve `dropped_events` sayacı artırılır (FR-013).
- Overhead kalibrasyonu: başlangıçta ardışık `dwt_now()` çağrıları ile boş ölçüm maliyeti hesaplanır (FR-012).

### 4.3 Buton ve Debounce
- EXTI0 yükselen kenar.
- Debounce stratejisi TBD-03. Aday yöntemler:
  1. ISR'de ilk kenarı damgala, EXTI'yi maskele; ResponseTask sonrası kilitlenme süresi (ör. 50 ms) dolunca yeniden aç.
  2. ISR'de zaman damgasına göre kilitlenme penceresi (yazılımsal).
- Tercih edilen: ilk kenar her zaman ölçülür, sonraki sıçramalar ölçüme dahil edilmez.

### 4.4 `load` — Yük Üreteçleri
Ortak arayüz:
```c
typedef struct {
    const char *name;
    void (*start)(void);
    void (*stop)(void);
    int  (*set_param)(uint8_t id, int32_t value);
} load_gen_t;
```

| Yük | Parametreler (öneri) |
|---|---|
| CPU (LoadTask_H/M/L) | enable, öncelik, çalışma süresi (µs), periyot (ms) |
| Kesme (TIM7) | enable, frekans (Hz), ISR içi meşgul süre (µs), NVIC önceliği |
| Kritik bölge | enable, tür (`taskENTER_CRITICAL` / `vTaskSuspendAll` / `__disable_irq`), süre (µs), periyot (ms) |
| İletişim | telemetri modu (olay başı / toplu), ek dolgu verisi hızı (B/s) |
| (İleride) Edge AI | Çıkarım görevi — ayrı faz |

Meşgul döngüler süre ölçümünü DWT ile yapar (derleyici optimizasyonundan bağımsız olması için).

### 4.5 `config` — Parametre Deposu
- Tüm ayarlar tek bir `app_config_t` yapısında, her parametrenin kimliği, tipi, min/max değeri bir tabloda tanımlıdır.
- PC yazma komutları doğrulanır; geçersiz değer reddedilir.
- Senaryo profilleri (S0…Sn) bu tablonun önceden tanımlı değer setleridir (TBD-08).

### 4.6 `proto` — Protokol
- Detaylar: **[06_PROTOCOL_SPEC](06_PROTOCOL_SPEC.md)** (detaylandırılacak).
- RX: USART2 DMA (circular) + IDLE line kesmesi → CommandTask'a bildirim.
- TX: DMA ile, TelemetryTask tek sahip (mutex gerekmez).

## 5. FreeRTOSConfig.h (öneri)
| Ayar | Değer | Neden |
|---|---|---|
| configUSE_PREEMPTION | 1 | |
| configUSE_TIME_SLICING | 1 | Eş öncelik deneyleri |
| configTICK_RATE_HZ | 1000 | TBD |
| configUSE_TICKLESS_IDLE | 0 | Ölçümü bozar |
| configCHECK_FOR_STACK_OVERFLOW | 2 | NFR-006 |
| configUSE_MALLOC_FAILED_HOOK | 1 | NFR-006 |
| configUSE_IDLE_HOOK | 1 | CPU yükü (TBD-09) |
| configGENERATE_RUN_TIME_STATS | 1 | Görev bazlı CPU payı |
| configUSE_TRACE_FACILITY | 1 | `uxTaskGetSystemState` |
| configSUPPORT_STATIC_ALLOCATION | 1 | NFR-005 |
| configASSERT | Tanımlı → kırmızı LED + durma | NFR-006 |
| Heap | heap_4 | |

## 6. Derleme Profilleri
| Profil | Optimizasyon | Kullanım |
|---|---|---|
| Debug | -O0 / -Og | Geliştirme |
| Measure | -O2 | **Tüm raporlanan ölçümler bu profilde** |

Ölçüm sonuçlarıyla birlikte firmware sürümü, git hash ve derleme profili PC'ye bildirilir.
