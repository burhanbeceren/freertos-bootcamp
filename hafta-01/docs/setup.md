# Kurulum: Donanım, Araçlar, Derleme, Yükleme, Ölçüm

## 1. Donanım ve bağlantılar

| Bileşen | Not |
|---|---|
| STM32F407G-DISC1 (MB997) | Mini-USB (CN1) ile ST-LINK: besleme + programlama |
| USB-TTL dönüştürücü | **3,3 V lojik** (CP2102 / CH340 / FT232). DISC1'de ST-LINK sanal COM portu yoktur. |

```
 STM32F407G-DISC1              USB-TTL (3,3 V)
 PA2  (USART2_TX)  ─────────►  RXD
 PA3  (USART2_RX)  ◄─────────  TXD
 GND               ──────────  GND
                               VCC  → BAĞLAMAYIN
```

| Pin | Görev |
|---|---|
| PA0 | B1 kullanıcı butonu (EXTI0, iki kenar, kartta pull-down + RC) |
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

1. **Port**'u seçin → **Bağlan**. Üst satırda FW, git ve 168 MHz bilgisi görünmelidir.
2. Senaryoyu seçin → **1 · Senaryoyu ayarla (SCN)**. MCU önceki TX'i bitirir, kayıtları sıfırlar.
3. **2 · Başlat**. Turuncu LED yanar. **5 s geri sayım** sırasında butona basmayın.
4. "Ölçüm" durumunda butona **en az 30 kez** basın. Basışlar arasında en az 0,5 s olsun ve ritmi bilerek değiştirin. Her basışta mavi LED değişir ve arayüzde "Butona basıldı · Olay N" görünür.
5. **3 · Durdur ve kayıtları al**. STOP → DUMP otomatik çalışır. Arayüz `measurements/Sx.csv`, `Sx_counters.csv` ve `raw/Sx_session.log` dosyalarını kaydeder.
6. S0'dan S5'e kadar tekrarlayın. Ardından:
   ```bash
   cd hafta-01
   interface/.venv/Scripts/python analysis/scripts/analyze.py
   ```
   Bu komut `measurements/summary.csv`, `analysis/plots/*.png` ve `analysis/results_tables.md` dosyalarını üretir.

**Doğrulama kontrol listesi (her senaryo):**
`CNT,tel_period_min_us/max_us` beklenen periyoda yakın mı (S1 100000, S2 20000, S3–S5 10000)? `CNT,work_min_us/max_us` S4'te ≈ 2000, S5'te ≈ 5000 mi? `CNT,log_overflow` = 0 mı?
