# UART Protokolü (MCU ↔ PC)

Fiziksel katman: USART2, 115200 baud, 8N1, akış kontrolü yok. Tüm satırlar ASCII'dir ve LF (`\n`) ile biter.

## 1. MCU → PC

### Ölçüm sırasında (sabit 64 bayt)
63 bayt ASCII metin, boşlukla 63 bayta tamamlanır, 64. bayt LF'dir. Metin 63 baytı aşarsa mesaj **kesilmez**; gönderilmez ve `fmt_error` sayacı artar.

| Satır | Örnek | Alanlar |
|---|---|---|
| TEL | `TEL,1042,S3,52348817,0,726` | sıra no, senaryo, MCU üretim anı (µs), bu periyottaki CPU işi (µs), sağlama (işin sonucu, alt 16 bit) |
| BTN | `BTN,17,S3,PRESSED` | olay kimliği, senaryo, yanıt metni ("butona basıldı") |

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
| `DUMP` | LOG + CNT + END | Ölçüm durmuşken; aksi halde `NAK,DUMP,running` |

## 3. Tek sahiplik
UART'a yalnızca `UartTxTask` yazar: TEL/BTN kuyruktan gelir, komut yanıtlarını ise görev kendisi üretir. RX baytları USART2 ISR'ında satıra birleştirilir. Satır, komut kuyruğu üzerinden **yine UartTxTask'a** iletilir. Bu yüzden komut yanıtları ölçülen mesajlarla aynı hat üzerinde yarışmaz.
