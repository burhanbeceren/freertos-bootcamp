# Mimari Karar Kayıtları (ADR)

## ADR-001: Toolchain — STM32CubeIDE araçları + HAL · Kabul
CubeIDE 1.10.1'in gcc 10.3 ve make araçları, STM32CubeF4 V1.26.1 HAL'i ile kullanılıyor. Proje **Makefile** tabanlıdır ve kaynaklar depoya kopyalanmıştır. Böylece CubeMX'e gerek kalmadan, depo tek başına derlenebilir. CubeIDE'de "Makefile project" olarak açılıp hata ayıklanabilir.

## ADR-002: PC arayüzü — Python + PySide6 + pyqtgraph · Kabul
Arayüz ve analiz aynı `metrics.py` modülünü paylaşır; tek doğruluk kaynağı budur.

## ADR-003: Haberleşme — USART2 + harici USB-TTL, DMA TX · Kabul
Bu karttaki ST-LINK/V2-A'nın sanal COM portu (Windows'ta COM3) MCU'nun PA2/PA3 pinlerine bağlı değildir. Kartta doğrulandı: firmware çalışırken COM3'ten hiçbir bayt gelmedi. USB CDC, USB yığını nedeniyle ek bir gecikme kaynağı olurdu. DMA kullanıldığı için bayt başına kesme yükü oluşmaz.

## ADR-004: Zaman damgası — TIM2 1 MHz (önceki taslaktaki DWT yerine) · Kabul, **değiştirildi**
İlk taslakta DWT CYCCNT seçilmişti. Görev standardı µs cinsinden CSV (`t0_us…t4_us`) ve mod 2³² farklar istiyor. DWT/168 bölümü sarmada tutarsız olur ve CYCCNT 25,6 s'de sarar. TIM2 ise 32 bit ve 1 MHz'dir: tek register okumasıyla okunur, ISR'dan güvenlidir ve 71,6 dakikada sarar. Harici ölçüm cihazı (lojik analizör) kullanılmıyor; sonuçlar UART üzerinden arayüzde görülür.

## ADR-005: Uygulama kodunda yerel FreeRTOS API · Kabul
CMSIS-RTOS sarmalayıcıları kullanılmıyor. Ölçülen yol şeffaf kalıyor.

## ADR-006: UART'ın tek sahibi UartTxTask; RX de ona bağlı · Kabul
Komut yanıtları ve DUMP dahil, hatta yalnızca UartTxTask yazar. PC komutları RX ISR → cmdQ → queue set yoluyla aynı göreve gelir. Dördüncü bir uygulama görevi eklenmez; "3 uygulama görevi" kuralı korunur.

## ADR-007: RX, HAL dışında işlenir · Kabul
`HAL_UART_Receive_IT` ile `HAL_UART_Transmit_DMA` aynı `__HAL_LOCK`'u paylaşır. ISR'dan yeniden kurma, TX başlatmayla çakışınca RX kalıcı olarak kapanabilir. RX baytı `USART2_IRQHandler` içinde SR→DR okumasıyla alınır.

## ADR-008: Debounce iki kenarlı ve "sessizlik" tabanlı · Kabul
Yalnızca yükselen kenarla çalışan bir filtre, 30 ms'den uzun basılı tutulan butonun **bırakma** sıçramalarını yeni basış sanabilir. İki kenar izlenir; bir yükselen kenar ancak önceki herhangi bir kenardan ≥ 30 ms sonra gelirse basıştır. İlk kenar gecikmesiz kabul edilir; t₀ ertelenmez.

## ADR-010: Deney kontrolü kartta, PC yalnızca dinler · Kabul
Denenen iki USB-TTL adaptörün PC → kart yönü çalışmadı. PL2303HXA sürücü tarafından engellendi; FT232 modülünün TX'i LOW'da kaldı. Görevin PC tarafı gereksinimi telemetriyi **almaktır**. Bu yüzden senaryo seçimi ve START mavi butona (boşta kısa/uzun basış) verildi. STOP + DUMP, 30. olayın yanıtı hattan çıkınca otomatik yapılır. Komutlar aynı cmdQ → UartTxTask yolundan geçer: UART'ın tek sahibi ve 3 görev kuralı korunur. PC komutları çalışan bir adaptörle hâlâ kullanılabilir.

## ADR-009: Zaman çizelgesi gerçek ölçümden çizilir · Kabul
Zaman çizelgesi, R ve deadline payı; kaydedilen gerçek olayların t₀…t₄ damgalarından `analyze.py` ile üretilir. Simülasyon/model kullanılmaz.

## ADR-011: Gecikme azaltma varyantları A/B/C · Kabul
Amaç, telemetri ve CPU yükü altında buton yanıtının kaymasını en aza indirmek ve her iyileştirmenin etkisini ayrı ayrı göstermektir. Varyantlar çalışma anında `VAR` komutuyla seçilir:
- **A — görev standardı:** tek TX FIFO, öncelik Telemetry 3 > Button 2 > UartTx 1. Karşılaştırmanın referansıdır.
- **B — öncelikli yanıt kuyruğu:** BTN yanıtı ayrı bir kuyruğa (8) gider. UartTxTask her uyanışta önce bu kuyruğa bakar. Kuyruktaki TEL birikmesinin arkasında bekleme (t₃−t₂) ortadan kalkar; hatta o anda giden mesaj yine beklenir.
- **C — B + görev önceliği Button 4 > UartTx 3 > Telemetry 2:** yanıt, CPU işinin bitmesini beklemez (t₁−t₀). UART görevi CPU işi yüzünden aç kalmaz (S5 birikmesi).

Görevin standardı A'dır. B ve C, standardın neden ve ne kadar kaydığını gösteren ayrı ölçümlerdir.

## ADR-012: EXTI enjeksiyonu ile tekrarlanabilir uyarım · Kabul
TIM7, 0,5–0,9 s arası rastgele aralıklarla EXTI0 hattını yazılımla (SWIER) tetikler. ISR'dan sonraki ölçüm yolu fiziksel basışla birebir aynıdır. Doğrulama: A varyantında enjeksiyonla S0/S3/S4 için 5,59 / 7,03 / 8,43 ms ölçüldü; fiziksel butonla 5,59 / 7,08 / 8,50 ms. Uyarım otomatik olduğu için 18 deney (3 varyant × 6 senaryo) insan zamanlaması olmadan, her biri 50 olayla yapılabilir. Veriler `runs/<V>-INJ/` altında, fiziksel buton verilerinden ayrı tutulur. Ek görev yoktur: TIM7 bir kesmedir.

## ADR-013: PC → kart komutları için ST-LINK posta kutusu · Kabul
FT232 modülünün TX hattı çalışmadı. ST-LINK zaten programlama için takılıdır. Kartın RAM'inde sabit adreste (0x20000000, `.mailbox` NOLOAD bölümü) 20 baytlık bir posta kutusu vardır ve CubeProgrammer CLI ile yaklaşık 0,1 s'de yazılır. UartTxTask bunu 100 ms'de bir yoklar ve UART komutlarıyla aynı işleyiciye verir. Yanıtlar yine UART RX'ten gelir. UART'ın tek sahibi ve 3 görev kuralı korunur.
