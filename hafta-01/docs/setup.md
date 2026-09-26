# Kurulum: Donanım, Araçlar, Derleme, Yükleme, Ölçüm

## 1. Donanım ve bağlantılar

| Bileşen | Not |
|---|---|
| STM32F407G-DISC1 (MB997) | Mini-USB (CN1) ile ST-LINK: besleme + programlama |
| USB-TTL dönüştürücü | **3,3 V lojik** (bu çalışmada FT232 modülü kullanıldı). ST-LINK'in COM portu ("STLink Virtual COM Port") bu kartta PA2/PA3'e bağlı **değildir**; arayüzde USB-TTL'nin portunu seçin. |

```
 STM32F407G-DISC1              USB-TTL (3,3 V)
 PA2  (USART2_TX)  ─────────►  RXD        (zorunlu: telemetri ve ölçüm verisi)
 PA3  (USART2_RX)  ◄─────────  TXD        (isteğe bağlı: PC'den komut)
 GND               ──────────  GND        (zorunlu)
                               VCC  → BAĞLAMAYIN
```

Ölçüm için yalnızca **kart → PC** yönü (PA2 → RXD) gereklidir. Deney akışı kartın mavi butonuyla yönetilir (§6).

> **Adaptör notu:** Bu çalışmada iki adaptörün PC → kart yönü çalışmadı. PL2303HXA güncel Prolific sürücüsüyle hiç açılmadı. FT232 modülünde TX hep LOW kaldı; loopback testi (TXD↔RXD) başarısız oldu. Bu yüzden ölçümler **yalnızca RX** ile yapıldı. Adaptörünüzü denemek için TXD'yi RXD'ye bağlayıp bir terminalden gönderdiğinizin geri geldiğini kontrol edin.

| Pin | Görev |
|---|---|
| PA0 | B1 mavi USER butonu (EXTI0, iki kenar, kartta pull-down + RC). **Ölçülen buton** ve deney kontrolü; kablo gerekmez. |
| PE7 | İsteğe bağlı ikinci kontrol butonu (diğer ucu GND, dahili pull-up). Kullanılmadı. |
| PA2 / PA3 | USART2 TX / RX, AF7 |
| PD12 yeşil | Açılış tamamlandı |
| PD13 turuncu | Ölçüm aktif (START…STOP) |
| PD14 kırmızı | Hata: assert, HardFault, stack overflow, malloc |
| PD15 mavi | Buton yanıtı (ButtonTask her olayda toggle eder) |

## 2. Araç sürümleri (bu depoda kullanılan)

| Araç | Sürüm |
|---|---|
| STM32CubeIDE | 1.10.1 (içindeki araçlar kullanıldı) |
| arm-none-eabi-gcc | GNU Tools for STM32 10.3-2021.10 |
| GNU make | CubeIDE eklentisi `make.win32 2.0.100` |
| STM32CubeF4 | V1.26.1 (HAL, CMSIS, FreeRTOS V10.3.1 depoya kopyalandı) |
| STM32CubeProgrammer | CLI, `make flash` için |
| Python | 3.11 |
| PySide6 / pyqtgraph / pyserial / matplotlib | 6.11 / 0.14 / 3.5 / 3.11 |
| İşletim sistemi | Windows 11 |

## 3. Firmware derleme ve yükleme

### 3.1 Komut satırı (Git Bash)
```bash
cd hafta-01/firmware
export PATH="/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.10.3-2021.10.win32_1.0.0.202111181127/tools/bin:/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.make.win32_2.0.100.202202231230/tools/bin:$PATH"
make -j8            # build/hafta01.elf, .hex, .bin
make flash          # STM32_Programmer_CLI ile SWD üzerinden yazar ve reset atar
```
Farklı bir CubeIDE sürümünde yollar değişir: `C:\ST\STM32CubeIDE_*\STM32CubeIDE\plugins\` altında `gnu-tools-for-stm32` ve `make` klasörlerini bulun.

### 3.2 STM32CubeIDE ile (hata ayıklama için)
1. *File → New → Makefile Project with Existing Code*. Konum `hafta-01/firmware`, araç zinciri *MCU ARM GCC*.
2. *Project → Build Project*: Makefile kullanılır.
3. *Run → Debug Configurations → STM32 C/C++ Application*: `build/hafta01.elf`, hata ayıklayıcı ST-LINK (SWD).

### 3.3 Açılış kontrolü
Kart açıldığında yeşil LED yanar ve UART'tan şu satırlar gelir:
```
BOOT,hafta01-1.0.0
INF,fw,hafta01-1.0.0
INF,sysclk_hz,168000000
INF,iters_per_ms,<kartınızın değeri>
...
ACK,INFO
```

## 4. Timer ve FreeRTOS ayarları (rapora yazılır)

| Ayar | Değer | Dosya |
|---|---|---|
| SYSCLK | 168 MHz (HSE 8 MHz, PLL M8 N336 P2 Q7) | `Core/Src/main.c` |
| Flash | 5 WS, prefetch + I/D cache | `main.c`, `stm32f4xx_hal_conf.h` |
| Zaman damgası | TIM2, PSC = 83 → 1 MHz, ARR = 0xFFFFFFFF | `App/Src/timebase.c` |
| HAL tick + RTOS tick | SysTick, 1 kHz, paylaşımlı | `Core/Src/stm32f4xx_it.c` |
| configTICK_RATE_HZ | 1000 | `Core/Inc/FreeRTOSConfig.h` |
| Preemption / time slicing | 1 / 1 | " |
| configUSE_TIMERS | 0 (timer servis görevi yok) | " |
| configMAX_SYSCALL_INTERRUPT_PRIORITY | 5 | " |
| Heap | heap_4, 24 KB | " |
| Stack kontrolü | configCHECK_FOR_STACK_OVERFLOW = 2 | " |
| NVIC | Grup 4; EXTI0 = 5, USART2 = 6, DMA1_Stream6 = 6, SysTick/PendSV = 15 | `button.c`, `stm32f4xx_hal_msp.c` |
| Derleme | `-O2 -g3 -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard` | `Makefile` |

## 5. Arayüzü başlatma
```bash
cd hafta-01/interface
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uart_monitor
```
Testler: `.venv/Scripts/python -m pytest -q`

## 6. Senaryo seçimi ve ölçüm adımları

Her senaryo S0…S5 için aynı sıra izlenir:

Deney kartın **mavi USER butonuyla** yönetilir. Arayüz yalnızca dinler.

| Durum | Mavi butona… | Sonuç |
|---|---|---|
| Boşta | kısa bas (< 1 s) | Sonraki senaryo (S0 → S1 → … → S5 → S0). Kayıt ve sayaçlar sıfırlanır. |
| Boşta | uzun bas (≥ 1 s) | START. Turuncu LED yanar, 5 s ısınma başlar; bu sürede basışlar kabul edilmez. |
| Ölçümde | her basış | Ölçülen olay (t₀…t₄) |
| Ölçümde | 30. kabul edilen basış | Yeni basış kabul edilmez. 30. olayın yanıtı telemetri ve CPU yükü açıkken hattan çıkınca STOP + DUMP otomatik çalışır. |

1. Arayüzde USB-TTL portunu seçin → **Bağlan**. FW ve 168 MHz bilgisi için gerekirse kartın siyah RESET butonuna basın.
2. Mavi butona kısa basarak senaryoyu seçin; arayüzde görünür.
3. Uzun basın → 5 s ısınmayı bekleyin.
4. **30 kez** basın. Basışlar arasında en az 0,5 s olsun ve ritmi bilerek değiştirin. Her basışta mavi LED değişir ve arayüzde "Butona basıldı · Olay N" görünür.
5. Deney kendiliğinden biter. Arayüz `measurements/Sx.csv`, `Sx_counters.csv` ve `raw/Sx_session.log` dosyalarını kaydeder, R grafiğini çizer.
6. S0'dan S5'e kadar tekrarlayın. Ardından:
   ```bash
   cd hafta-01
   interface/.venv/Scripts/python analysis/scripts/analyze.py
   ```
   Bu komut `measurements/summary.csv`, `analysis/plots/*.png`, `analysis/results_tables.md` ve `docs/zaman-cizelgesi.png` / `_tablo.md` dosyalarını üretir.

PC → kart yönü çalışan bir adaptörde arayüzdeki SCN / START / STOP düğmeleri de aynı akışı yönetir.

**Arayüzde sonuçları görmek:** Komut satırı gerekmez.

| Sekme | İçerik |
|---|---|
| BTN olayları | Canlı "Butona basıldı · Olay N" listesi |
| Sonuçlar | Son deneyin R grafiği (20 ms çizgisi), aşama ortalaması, istatistik ve kayıplar |
| Ham UART | Karttan gelen satırlar (TEL hariç) |
| Ölçümler (kayıtlı) | Seçilen senaryonun kayıtlı CSV'si: olay başına t₁−t₀…t₄−t₃, R, pay (kayıp kırmızı, geç turuncu) ve MCU sayaçları |
| Analiz ve grafikler | **▶ Analizi çalıştır**: tüm kayıtlı senaryolardan özet tablo + 5 grafik (olay → R, aşama ortalamaları, dağılımlar, faz, zaman çizelgesi). `analyze.py` ile aynı kod ve aynı dosyalar. Her kayıttan sonra otomatik yenilenir. |

**Doğrulama kontrol listesi (her senaryo):**
`CNT,tel_period_min_us/max_us` beklenen periyoda yakın mı (S1 100000, S2 20000, S3–S5 10000)? `CNT,work_min_us/max_us` S4'te ≈ 2000, S5'te ≈ 5000 mi? `CNT,log_overflow` = 0 mı?
