# 05 — Ölçüm Spesifikasyonu

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.0 | 2026-09-26 | **İskelet — kullanıcı tarafından detaylandırılacak** |

> Bu doküman bilinçli olarak boş bırakılmıştır. Aşağıdaki başlıklar doldurulacak alanları gösterir. `[ÖNERİ]` ile işaretli içerik yalnızca başlangıç noktasıdır; kesinleşmiş değildir.

## 1. Ölçüm Prensibi
- Zaman kaynağı: DWT CYCCNT, 168 MHz (bkz. ADR-004).
- Ölçümün göremedikleri: fiziksel basış → EXTI, NVIC giriş gecikmesi (bkz. 01 §7).
- _Detaylandırılacak._

## 2. Zaman Damgası Noktaları (TBD-01)
| Kimlik | Konum | Anlamı |
|---|---|---|
| t0 | _TBD_ | `[ÖNERİ]` EXTI0 ISR ilk komut |
| t1 | _TBD_ | `[ÖNERİ]` ResponseTask bildirimden uyandıktan sonraki ilk komut |
| t2 | _TBD_ | `[ÖNERİ]` Yanıt GPIO set edildikten hemen sonra |
| … | | |

## 3. "Yanıt" Tanımı (TBD-02)
_Detaylandırılacak._

## 4. Olay Kaydı Yapısı (TBD-07)
```c
/* [ÖNERİ] — kesinleşmedi */
typedef struct {
    uint32_t seq;
    uint32_t t0, t1, t2;
    uint16_t scenario_id;
    uint16_t flags;        /* overflow, debounce, kayıp vb. */
    /* sistem bağlamı alanları: TBD */
} meas_event_t;
```

## 5. Türetilen Metrikler
| Metrik | Formül | Birim |
|---|---|---|
| _TBD_ | | çevrim / µs |

## 6. İstatistikler ve Jitter Tanımı (TBD-06)
_Detaylandırılacak._

## 7. Overhead Kalibrasyonu
_Detaylandırılacak._

## 8. Hata ve Geçersiz Ölçüm Kuralları
_Detaylandırılacak (sıçrama, üst üste binen olay, taşma, buffer dolması)._

## 9. Kabul Kriterleri (TBD-05)
_Detaylandırılacak._
