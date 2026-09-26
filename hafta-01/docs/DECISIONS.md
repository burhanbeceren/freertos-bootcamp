# Mimari Karar Kayıtları (ADR)

## ADR-001: Toolchain — STM32CubeIDE araçları + HAL · Kabul
CubeIDE 1.10.1'in gcc 10.3 ve make araçları, STM32CubeF4 V1.26.1 HAL'i ile kullanılıyor. Proje **Makefile** tabanlıdır ve kaynaklar depoya kopyalanmıştır. Böylece CubeMX'e gerek kalmadan, depo tek başına derlenebilir. CubeIDE'de "Makefile project" olarak açılıp hata ayıklanabilir.

## ADR-002: PC arayüzü — Python + PySide6 + pyqtgraph · Kabul
Arayüz ve analiz aynı `metrics.py` modülünü paylaşır; tek doğruluk kaynağı budur.

## ADR-003: Haberleşme — USART2 + harici USB-TTL, DMA TX · Kabul
Bu karttaki ST-LINK/V2-A'nın sanal COM portu (Windows'ta COM3) MCU'nun PA2/PA3 pinlerine bağlı değildir. Kartta doğrulandı: firmware çalışırken COM3'ten hiçbir bayt gelmedi. USB CDC, USB yığını nedeniyle ek bir gecikme kaynağı olurdu. DMA kullanıldığı için bayt başına kesme yükü oluşmaz.

## ADR-004: Zaman damgası — TIM2 1 MHz (önceki taslaktaki DWT yerine) · Kabul, **değiştirildi**
İlk taslakta DWT CYCCNT seçilmişti. Ödev standardı µs cinsinden CSV (`t0_us…t4_us`) ve mod 2³² farklar istiyor. DWT/168 bölümü sarmada tutarsız olur ve CYCCNT 25,6 s'de sarar. TIM2 ise 32 bit ve 1 MHz'dir: tek register okumasıyla okunur, ISR'dan güvenlidir ve 71,6 dakikada sarar. Harici ölçüm cihazı (lojik analizör) kullanılmıyor; sonuçlar UART üzerinden arayüzde görülür.

## ADR-005: Uygulama kodunda yerel FreeRTOS API · Kabul
CMSIS-RTOS sarmalayıcıları kullanılmıyor. Ölçülen yol şeffaf kalıyor.

## ADR-006: UART'ın tek sahibi UartTxTask; RX de ona bağlı · Kabul
Komut yanıtları ve DUMP dahil, hatta yalnızca UartTxTask yazar. PC komutları RX ISR → cmdQ → queue set yoluyla aynı göreve gelir. Dördüncü bir uygulama görevi eklenmez; "3 uygulama görevi" kuralı korunur.

## ADR-007: RX, HAL dışında işlenir · Kabul
`HAL_UART_Receive_IT` ile `HAL_UART_Transmit_DMA` aynı `__HAL_LOCK`'u paylaşır. ISR'dan yeniden kurma, TX başlatmayla çakışınca RX kalıcı olarak kapanabilir. RX baytı `USART2_IRQHandler` içinde SR→DR okumasıyla alınır.

## ADR-008: Debounce iki kenarlı ve "sessizlik" tabanlı · Kabul
Yalnızca yükselen kenarla çalışan bir filtre, 30 ms'den uzun basılı tutulan butonun **bırakma** sıçramalarını yeni basış sanabilir. İki kenar izlenir; bir yükselen kenar ancak önceki herhangi bir kenardan ≥ 30 ms sonra gelirse basıştır. İlk kenar gecikmesiz kabul edilir; t₀ ertelenmez.

## ADR-010: Deney kontrolü kartta, PC yalnızca dinler · Kabul
Denenen iki USB-TTL adaptörün PC → kart yönü çalışmadı. PL2303HXA sürücü tarafından engellendi; FT232 modülünün TX'i LOW'da kaldı. Ödevin PC tarafı gereksinimi telemetriyi **almaktır**. Bu yüzden senaryo seçimi ve START mavi butona (boşta kısa/uzun basış) verildi. STOP + DUMP, 30. olayın yanıtı hattan çıkınca otomatik yapılır. Komutlar aynı cmdQ → UartTxTask yolundan geçer: UART'ın tek sahibi ve 3 görev kuralı korunur. PC komutları çalışan bir adaptörle hâlâ kullanılabilir.

## ADR-009: Zaman çizelgesi gerçek ölçümden çizilir · Kabul
Zaman çizelgesi, R ve deadline payı; kaydedilen gerçek olayların t₀…t₄ damgalarından `analyze.py` ile üretilir. Simülasyon/model kullanılmaz.
