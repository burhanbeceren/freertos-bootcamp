# Gereksinim — Yük Altında Buton Yanıt Süresi

| Sürüm | Tarih | Durum |
|---|---|---|
| v1.0 | 2026-09-26 | Onaylandı (deney standardı) |

## 1. Gereksinim cümlesi

> **REQ-01:** Kullanıcı butonuna basıldığında, orta öncelikli `ButtonTask` "butona basıldı" yanıtını (`BTN,<id>,<senaryo>,PRESSED`) üretmeli ve bu yanıt UART'tan tamamen çıkmalıdır. Buton ISR girişinden yanıtın son bitinin hattan çıkışına kadar geçen süre için **R = t₄ − t₀ ≤ 20 ms** sağlanmalıdır. Bu koşul §4'teki çalışma koşullarında ve S0–S5 senaryolarının her birinde geçerlidir.

20 ms bu ödev için seçilmiş bir eşiktir, bir ürün standardı değildir.

## 2. Başlangıç ve bitiş: ölçülen aralığın sınırları

Beş nokta da **aynı kart saatinden** alınır: TIM2, 1 MHz, 32 bit, serbest çalışan sayaç. PC saati hiçbir hesapta kullanılmaz.

| Nokta | Nerede kaydedilir? | Kod | Yorum |
|---|---|---|---|
| **t₀ — BAŞLANGIÇ** | `EXTI0_IRQHandler` girişinde | [button.c](../firmware/App/Src/button.c) | 30 ms filtresinin kabul ettiği kenarın zamanı. Fiziksel basma anı **değildir**. |
| t₁ | `ButtonTask`, `xQueueReceive` döndükten hemen sonra | button.c | Olay aktarımı ve CPU beklemesi dahildir. |
| t₂ | Yanıt için `xQueueSend(txQ)` çağrısından hemen önce | button.c | Başarılı gönderimde ölçüm zinciri devam eder. |
| t₃ | `UartTxTask`, `HAL_UART_Transmit_DMA` çağrısından hemen önce | [uart_tx.c](../firmware/App/Src/uart_tx.c) | İlk fiziksel bitle aynı an değildir. |
| **t₄ — BİTİŞ** | `HAL_UART_TxCpltCallback` (USART **TC** kesmesi) | uart_tx.c | Son stop bitinden sonraki ISR/callback gözlem zamanı. "DMA bitti" anı değildir. |

**Deadline:** D = 20 ms. **Deadline payı** = D − R. Pay pozitifse deadline karşılanmıştır.

### Aralığın içinde kalanlar
ISR gövdesi, ISR→görev aktarımı, zamanlayıcı beklemesi, yanıtın hazırlanması, TX FIFO bekleme süresi, UART başlatma, 64 baytın hat süresi (5,556 ms) ve TC gözlemi.

### Aralığın dışında kalanlar (ölçülemez, açıkça belirtilir)
- Fiziksel basış → EXTI arası: buton mekaniği, karttaki RC filtre, giriş senkronizasyonu.
- NVIC kesme giriş gecikmesi: yaklaşık 12 çevrim + flash bekleme durumu (≈ 0,1 µs mertebesi).
- PC'nin baytı alması, USB-TTL gecikmesi, işletim sistemi ve arayüz gecikmesi.

## 3. Olay durumları

Her kabul edilen olay aşağıdaki durumlardan biriyle kapanır:

| Durum | Anlamı | Deadline sayımı |
|---|---|---|
| `ok` | t₄ kaydedildi | R ≤ 20 ms ise karşılandı, değilse **geç** |
| `btn_drop` | Buton kuyruğu (8) doluydu | Karşılanmadı |
| `tx_drop` | TX kuyruğu (16) doluydu | Karşılanmadı |
| `tx_error` | UART başlatma veya format hatası | Karşılanmadı |
| `timeout` | TC 1 s içinde gelmedi veya deney sonunda tamamlanmadı | Karşılanmadı |

Kayıp yanıtlar **asla** "deadline karşılandı" diye sayılmaz. Eksik zaman 0 yazılmaz, boş bırakılır.

## 4. Çalışma koşulları (karşılaştırırken değiştirilmez)

| Ayar | Değer | Neden |
|---|---|---|
| Kart / MCU | STM32F407G-DISC1, STM32F407VGT6 | — |
| Saat | HSE 8 MHz → PLL → SYSCLK 168 MHz; AHB 168, APB1 42, APB2 84 MHz | Aynı CPU hızı |
| Flash | 5 bekleme durumu; ART prefetch + I/D cache açık | Aynı komut yürütme süresi |
| Zaman damgası | TIM2, 1 MHz (PSC = 83), 32 bit, taşma ≈ 71,6 dk | 1 µs çözünürlük |
| RTOS | FreeRTOS V10.3.1, preemptive, time slicing açık, tick 1000 Hz, timer görevi yok | Aynı zamanlayıcı |
| Görevler | TelemetryTask 3 > ButtonTask 2 > UartTxTask 1 (Idle 0) | Aynı öncelik ilişkisi |
| Kesmeler | EXTI0 = 5, USART2 = 6, DMA1_Stream6 = 6; `MAX_SYSCALL` = 5 | FromISR API güvenli |
| UART | USART2 PA2/PA3, **115200 baud, 8N1** | Aynı hat süresi |
| Mesaj boyu | Her TEL/BTN mesajı **64 bayt** (63 ASCII + boşluk dolgusu + LF) | Paket boyu sabit |
| Kuyruklar | Buton: **8 olay**, TX: **16 mesaj**, FIFO | Aynı tampon davranışı |
| TX yöntemi | DMA; tamamlanana (TC) kadar `UartTxTask` bloklanır; zaman aşımı 1 s | Polling yükü yok |
| Debounce | İlk kenar kabul, 30 ms içindeki tekrarlar sayılıp atılır | Aynı olay tanımı |
| Derleme | arm-none-eabi-gcc 10.3-2021.10, `-O2 -g3`, newlib-nano | Aynı kod |
| Kayıt | RAM'de 128 olay (≥ 64), taşma sayacı | Kayıt kaybı görünür |

## 5. Senaryolar: önce frekans, sonra CPU yükü

| ID | Telemetri | Ek CPU işi (TelemetryTask, her periyot) | Hedef |
|---|---|---|---|
| S0 | Kapalı | Yok | Referans |
| S1 | 10 Hz · 100 ms | Yok | Düşük telemetri |
| S2 | 50 Hz · 20 ms | Yok | Orta telemetri |
| S3 | 100 Hz · 10 ms | Yok | Yüksek telemetri |
| S4 | 100 Hz · 10 ms | ≈ 2 ms (≈ %20 ek CPU) | Ek CPU yükü |
| S5 | 100 Hz · 10 ms | ≈ 5 ms (≈ %50 ek CPU) | Daha yüksek CPU yükü |

İki bütçe ayrı tutulur ve **toplanmaz**:
- **CPU:** U_ek ≈ C_ek × f. Bu değer 100 Hz × 2 ms ≈ %20 ve 100 Hz × 5 ms ≈ %50'dir.
- **UART hattı** (yalnız telemetri): 64 B × 10 bit × f / 115200. Bu değer 10 Hz'de %5,6, 50 Hz'de %27,8, 100 Hz'de %55,6'dır. Buton mesajları buna ek yük getirir.

CPU işi sabit iterasyonlu bir xorshift döngüsüdür. Açılışta kartta kalibre edilir (`INF,iters_per_ms`). Her periyotta gerçekten ölçülen iş süresi `CNT,work_min_us / work_max_us` ile raporlanır. Kesmeler kapatılmaz; `vTaskDelay` kullanılmaz.

## 6. Deney prosedürü (her senaryoda aynı sıra)

1. Senaryoyu seçin (mavi butona kısa basış veya `SCN,Sx`). Önceki TX biter; kayıtlar ve sayaçlar sıfırlanır.
2. Başlatın (uzun basış veya `START`). Frekansı, 64 baytlık mesaj boyunu ve CPU işini doğrulayın. **5 s ısınma** uygulayın; MCU bu sürede basışları kabul etmez.
3. **30 basış** yapın. Basışlar arasında **en az 0,5 s** olsun ve zamanlamayı değiştirin.
4. 30. olayın yanıtı hattan çıkınca MCU telemetriyi durdurur, TX'i tamamlar (ya da timeout kaydeder) ve veriyi dışarı aktarır (DUMP). PC'den `STOP`/`DUMP` ile de yapılabilir.
5. Ham CSV'yi saklayın; grafikleri aynı ham veriden üretin.

Toplam en az 6 × 30 = **180 kabul edilen olay**. Kayıplar ve hatalar ayrıca raporlanır, sonuçtan gizlenmez.

## 7. Kabul ölçütleri (rapor için)

Her senaryo için şunlar raporlanır:
- Başarılı ölçüm sayısı.
- R'nin minimum, ortalama ve **gözlenen** maksimum değeri.
- 20 ms'yi aşan tamamlanmış yanıt sayısı.
- `drop`, `tx_error`, `timeout` ve kayıt kaybı sayıları.
- Aşama sürelerinin karşılaştırması.

Gözlenen maksimum, kanıtlanmış bir worst-case değildir.
