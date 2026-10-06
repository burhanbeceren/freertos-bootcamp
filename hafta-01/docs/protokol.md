# UART Protokolü (MCU ↔ PC)

Fiziksel katman: USART2, 115200 baud, 8N1, akış kontrolü yok. Tüm satırlar ASCII'dir ve LF (`\n`) ile biter.

## 1. MCU → PC

### Ölçüm sırasında (sabit 64 bayt)
63 bayt ASCII metin, boşlukla 63 bayta tamamlanır, 64. bayt LF'dir. Metin 63 baytı aşarsa mesaj **kesilmez**; gönderilmez ve `fmt_error` sayacı artar.

| Satır | Örnek | Alanlar |
|---|---|---|
| TEL | `TEL,1042,S3,52348817,0,726,1,422,2930` | sıra no, senaryo, MCU üretim anı (µs), bu periyottaki CPU işi (µs), sağlama (işin sonucu, alt 16 bit), **TX kuyruğu doluluğu**, **sıcaklık (0,1 °C)**, **VDDA (mV)** |
| BTN | `BTN,17,S3,PRESSED,180193870,180193878` | olay kimliği, senaryo, yanıt metni ("butona basıldı"), **t₀**, **t₁** (canlı aşama gösterimi için) |

FW 1.0.0 satırları (TEL'de 6, BTN'de 4 alan) da okunur; ek alanlar isteğe bağlıdır.

### Ölçüm dışında (değişken uzunluk)
Bu satırlar yalnızca komut yanıtı olarak gönderilir; telemetri ve ölçüm hattına karışmaz.

| Satır | Örnek | Ne zaman |
|---|---|---|
| BOOT | `BOOT,hafta01-1.0.0` | Açılış |
| INF | `INF,sysclk_hz,168000000` | INFO |
| ACK / NAK | `ACK,SCN,S3` · `NAK,DUMP,running` | Her komut |
| LOG | `LOG,S3,18,1500000,1502100,1502400,,,tx_drop` | DUMP (her olay için bir satır) |
| CNT | `CNT,tel_tx_drop,0` | DUMP (sayaçlar) |
| END | `END,DUMP,S3` | DUMP sonu |

LOG alan sırası: `senaryo,event_id,t0,t1,t2,t3,t4,durum`. Eksik zaman boş bırakılır. CSV satırı bu alanlardan birebir oluşturulur.

## 2. PC → MCU (komutlar)

| Komut | Etki | Koşul |
|---|---|---|
| `PING` | `ACK,PING` | Her zaman |
| `INFO` | INF satırları + `ACK,INFO` | Her zaman |
| `SCN,Sx` | TX kuyruğunu boşalt, kayıt + sayaçları sıfırla, senaryoyu ayarla | Ölçüm durmuşken |
| `START` | Kayıt + sayaçları sıfırla, telemetriyi başlat, 5 s sonra basışları kabul et | Ölçüm durmuşken |
| `STOP` | Basış kabulünü kapat, telemetriyi durdur, TX kuyruğunu gönder (TC 1 s timeout), tamamlanmayanları `timeout` yap | Her zaman |
| `DUMP` | LOG + CNT + INF (varyant/kaynak/olay) + END | Ölçüm durmuşken; aksi halde `NAK,DUMP,running` |
| `VAR,A\|B\|C` | Gecikme azaltma varyantı (öncelikler + yanıt kuyruğu) → `ACK,VAR,x` | Ölçüm durmuşken |
| `SRC,HW\|INJ` | Uyarım kaynağı: fiziksel buton / EXTI enjeksiyonu → `ACK,SRC,x` | Ölçüm durmuşken |
| `EVN,n` | Otomatik durdurma olay sayısı (1–128) → `ACK,EVN,n` | Ölçüm durmuşken |
| `EXTI` | 100 kez yazılım tetiği → `EXT,n,min,ort,maks,sysclk` (çevrim) | Ölçüm durmuşken |

`ACK,START` artık `ACK,START,<senaryo>,<varyant>,<kaynak>,<n>` biçimindedir.

### Kart üzerinden üretilen komutlar
PC → kart yönü olmadan da deney yürütülebilir. Buton ISR'ları aynı komut kuyruğuna şu metinleri bırakır; UartTxTask bunları PC komutu gibi işler ve aynı `ACK` satırlarını gönderir. Arayüz bu satırlardan durumu izler.

| Kaynak | Komut | Etki |
|---|---|---|
| Mavi buton, boşta kısa basış | `SCNNEXT` | Sonraki senaryo → `ACK,SCN,Sx` |
| Mavi buton, boşta uzun basış (≥ 1 s) | `START` | → `ACK,START,Sx` |
| 30. kabul edilen olay kapandı | (iç) | STOP + DUMP → `ACK,STOP,Sx`, LOG…, `END,DUMP,Sx` |
| PE7 butonu (isteğe bağlı) | `SCNNEXT` / `START` / `STOPDUMP` | Aynı |

## 3. PC → kart taşıyıcıları

| Taşıyıcı | Nasıl | Ne zaman |
|---|---|---|
| UART | USB-TTL TXD → PA3, satır + LF | Adaptörün TX'i çalışıyorsa |
| **ST-LINK posta kutusu** | `STM32_Programmer_CLI -c port=SWD mode=HOTPLUG -w32 0x20000000 <4 kelime metin> <seq>`. 16 bayt metin + 4 bayt sıra numarası; **seq en son yazılır**. Kart 100 ms'de bir yoklar ve aynı komut işleyicisine verir. | UART TX yoksa (bu çalışmadaki FTDI) |

Arayüz ve `runner` önce UART'tan `PING` dener; 1 s içinde `ACK,PING` gelmezse ST-LINK'e geçer. Her komutun yanıtı beklenmeden bir sonrakisi yazılmaz, çünkü posta kutusu tek kayıtlıktır. Ölçülen hatta (TEL/BTN) bu taşıyıcıların etkisi yoktur: komutlar yalnızca deney öncesinde/sonrasında gönderilir.

## 4. Tek sahiplik
UART'a yalnızca `UartTxTask` yazar: TEL/BTN kuyruktan gelir, komut yanıtlarını ise görev kendisi üretir. RX baytları USART2 ISR'ında satıra birleştirilir. Satır, komut kuyruğu üzerinden **yine UartTxTask'a** iletilir. Bu yüzden komut yanıtları ölçülen mesajlarla aynı hat üzerinde yarışmaz.
