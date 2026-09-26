# Yapay Zekâ Kullanımı

Bu projede **Claude (Anthropic, Claude Code masaüstü uygulaması)** bir mühendislik asistanı olarak kullanıldı. Aşağıda neyin yapay zekâyla üretildiği ve neyin insan tarafından doğrulanması gerektiği açıkça listelenmiştir.

## Yapay zekânın yaptıkları
| Alan | Ayrıntı |
|---|---|
| Gereksinim ve spesifikasyon | Ödev dokümanındaki (gereksinimler.docx) kuralların yorumlanıp `gereksinim.md`, `protokol.md`, `code-notes.md` ve `setup.md` olarak yazılması |
| Firmware | `firmware/App/*`, `Core/Src/main.c`, `stm32f4xx_it.c`, `stm32f4xx_hal_msp.c`, `FreeRTOSConfig.h`, `Makefile`. HAL, CMSIS ve FreeRTOS dosyaları ST'nin STM32CubeF4 V1.26.1 paketinden değiştirilmeden kopyalandı (`stm32f4xx_hal_conf.h` modül seçimi ve HSE = 8 MHz hariç). |
| PC arayüzü | `interface/uart_monitor/*` ve birim testleri |
| Analiz | `analysis/scripts/analyze.py` (ham CSV → özet, grafikler, gerçek olaylardan zaman çizelgesi) ve `analysis/analiz.md` (hipotez ve ölçüm planı) |

## Yapay zekânın doğruladıkları
- Firmware, CubeIDE 1.10.1 araç zinciriyle **sıfır uyarıyla** derlendi (`-Wall`, `-O2`).
- t₀ okumasının ISR'ın ilk komutları arasında olduğu disassembly ile kontrol edildi.
- Arayüz birim testleri (13 test) ve ekransız GUI açılış testi geçti.
- Firmware karta ST-LINK ile yüklendi. SWD üzerinden yazmaç okumalarıyla şunlar kontrol edildi: saat, TIM2, USART2, GPIO, EXTI. UART bağlantı sorunları (ST-LINK VCP'nin bağlı olmaması, adaptörlerin TX arızası) bu şekilde teşhis edildi.

## İnsan tarafından yapılanlar
- Bütün buton basışları (6 senaryo × 30) kullanıcı tarafından kart üzerindeki mavi butonla yapıldı. Kablolama da kullanıcıya aittir.
- `measurements/` altındaki veriler yalnızca bu gerçek deneylerden gelir. Yapay zekâ veri üretmedi veya değiştirmedi. Tek istisna: `S1_counters.csv` ve `S2_counters.csv` içindeki `INF,scenario` meta satırı arayüz hatası nedeniyle eski senaryoyu (S0) gösteriyordu ve düzeltildi. Ölçüm satırlarına dokunulmadı.
- `report.md` içindeki yorumlar gerçek veri görüldükten sonra yazıldı; sayılar `analyze.py` çıktısından alındı.

## İlke
Depodaki bütün ölçüm verileri, tablolar ve grafikler gerçek kart deneyinden üretilir.
