# Yapay Zekâ Kullanımı

Bu projede **Claude (Anthropic, Claude Code masaüstü uygulaması)** bir mühendislik asistanı olarak kullanıldı. Aşağıda neyin yapay zekâyla üretildiği ve neyin insan tarafından doğrulanması gerektiği açıkça listelenmiştir.

## Yapay zekânın yaptıkları
| Alan | Ayrıntı |
|---|---|
| Gereksinim ve spesifikasyon | Ödev dokümanındaki (gereksinimler.docx) kuralların yorumlanıp `gereksinim.md`, `protokol.md`, `code-notes.md` ve `setup.md` olarak yazılması |
| Firmware | `firmware/App/*`, `Core/Src/main.c`, `stm32f4xx_it.c`, `stm32f4xx_hal_msp.c`, `FreeRTOSConfig.h`, `Makefile`. HAL, CMSIS ve FreeRTOS dosyaları ST'nin STM32CubeF4 V1.26.1 paketinden değiştirilmeden kopyalandı (`stm32f4xx_hal_conf.h` modül seçimi ve HSE = 8 MHz hariç). |
| PC arayüzü | `interface/uart_monitor/*` ve birim testleri |
| Model | `analysis/model/*`: zaman çizelgesi ve hipotez tahminleri (**ölçüm değildir**) |
| Analiz | `analysis/scripts/analyze.py` ve `analysis/analiz.md` (hipotezler) |

## Yapay zekânın doğruladıkları (kartsız)
- Firmware, CubeIDE 1.10.1 araç zinciriyle **sıfır uyarıyla** derlendi (`-Wall`, `-O2`).
- t₀ okumasının ISR'ın ilk komutları arasında olduğu disassembly ile kontrol edildi.
- Arayüz birim testleri (13 test) ve ekransız GUI açılış testi geçti.
- Analiz betiği, modelden üretilmiş **sentetik** veriyle yalnızca geçici bir klasörde çalıştırılarak denendi. Bu veri depoya **eklenmedi**.

## Yapay zekânın YAPMADIKLARI ve insan doğrulaması gerekenler
- ❌ Kart üzerinde çalıştırma ve ölçüm. Oturum sırasında ST-LINK bağlı değildi.
- ❌ `measurements/` altındaki hiçbir veri yapay zekâ tarafından üretilmedi. Bu dosyalar yalnızca gerçek kart deneyinden gelmelidir.
- ⚠️ Kart üzerinde kontrol edilmesi gerekenler: 168 MHz saat (`INF,sysclk_hz`), UART çıkışı, buton filtresi (`bounce_rejected`), DMA/TC davranışı, `iters_per_ms` kalibrasyonu.
- ⚠️ `report.md` içindeki yorumlar ve hipotez kararları gerçek veri görüldükten sonra yazılmalıdır.

## İlke
Sentetik ya da model verisi hiçbir yerde gerçek sonuç gibi sunulmaz. Model çıktıları dosya adında veya başlığında "MODEL" olarak etiketlenmiştir.
