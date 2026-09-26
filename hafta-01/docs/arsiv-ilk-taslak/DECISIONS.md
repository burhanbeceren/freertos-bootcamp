# Mimari Karar Kayıtları (ADR)

Format: Bağlam → Karar → Sonuçlar. Durum: Önerildi / Kabul / Değiştirildi.

---

## ADR-001 — Toolchain: STM32CubeIDE + HAL
- **Tarih:** 2026-09-26 · **Durum:** Kabul
- **Bağlam:** Hızlı başlangıç, CubeMX ile pin/saat/FreeRTOS konfigürasyonu isteniyor.
- **Karar:** STM32CubeIDE + CubeMX + HAL.
- **Sonuçlar:** HAL'in ISR içi ek yükü ölçümlere yansır; kritik yollarda (EXTI ISR) HAL callback zinciri yerine doğrudan register erişimi tercih edilebilir — ölçüm tanımında netleştirilecek.

## ADR-002 — PC arayüzü: Python + PySide6 + pyqtgraph
- **Tarih:** 2026-09-26 · **Durum:** Kabul
- **Bağlam:** Canlı grafik, istatistik ve ileride Edge AI veri işleme ihtiyacı.
- **Karar:** Python 3.11+, PySide6, pyqtgraph, pyserial, numpy.
- **Sonuçlar:** Edge AI fazında (veri toplama, model eğitimi) aynı ekosistem kullanılabilir.

## ADR-003 — Haberleşme: USART2 + harici USB-TTL
- **Tarih:** 2026-09-26 · **Durum:** Kabul
- **Bağlam:** STM32F407G-DISC1'de ST-LINK sanal COM portu yok. USB CDC, USB stack'i nedeniyle kendisi bir gecikme kaynağı olurdu.
- **Karar:** USART2 (PA2/PA3), DMA ile, harici 3.3 V USB-TTL.
- **Sonuçlar:** Ek donanım gerekir. İletişim yükü deterministik ve ayrı bir senaryo (S7) olarak incelenebilir.

## ADR-004 — Ölçüm: yalnızca iç ölçüm (DWT CYCCNT)
- **Tarih:** 2026-09-26 · **Durum:** Kabul
- **Bağlam:** Harici lojik analizör/osiloskop kullanılmayacak.
- **Karar:** Tüm zaman damgaları DWT CYCCNT ile alınır.
- **Sonuçlar:**
  - (+) 1 çevrim çözünürlük, ek donanım yok.
  - (−) Fiziksel basış → ISR girişi aralığı ölçülemez; teorik olarak açıklanır.
  - (−) Ölçüm kendi kendini doğrular; bu yüzden VT-01…VT-04 doğrulama testleri zorunludur.
  - Test GPIO pinleri (PE7–PE10) ileride harici doğrulama eklenebilsin diye ayrılmıştır.

## ADR-005 — Uygulama kodunda yerel FreeRTOS API
- **Tarih:** 2026-09-26 · **Durum:** Önerildi
- **Bağlam:** CubeMX CMSIS-RTOS v2 sarmalayıcıları üretir; bunlar ek katman ve gizli davranış getirir.
- **Karar:** Uygulama katmanında `xTaskNotifyFromISR`, `vTaskPrioritySet` vb. yerel API kullanılır.
- **Sonuçlar:** Ölçülen yol daha şeffaf; CubeMX yeniden üretiminde çakışma yok (kod `App/` altında).
