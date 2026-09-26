# 06 — PC ↔ MCU Protokol Spesifikasyonu

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.0 | 2026-09-26 | **İskelet — kullanıcı tarafından detaylandırılacak** |

> Bu doküman bilinçli olarak boş bırakılmıştır. `[ÖNERİ]` ile işaretli içerik yalnızca başlangıç noktasıdır.

## 1. Fiziksel Katman
| Parametre | Değer |
|---|---|
| Arayüz | USART2, PA2 (TX) / PA3 (RX), 3.3 V TTL |
| Baud | _TBD_ `[ÖNERİ]` 921600 |
| Format | 8N1, akış kontrolü yok |

## 2. Çerçeve Formatı (TBD-04)
_Detaylandırılacak._ Karar verilecek konular:
- İkili mi, metin (ASCII/JSON satırı) mı?
- Senkronizasyon: başlık baytı / COBS / SLIP?
- Uzunluk alanı, mesaj tipi, sıra numarası
- Hata denetimi: CRC-16/CCITT, CRC-32?
- Endianness

## 3. Mesaj Tipleri
### 3.1 PC → MCU (Komutlar)
| Kod | Ad | Açıklama |
|---|---|---|
| _TBD_ | | `[ÖNERİ]` PING, GET_INFO, GET_PARAM, SET_PARAM, LOAD_SCENARIO, START, STOP, RESET_STATS |

### 3.2 MCU → PC (Yanıt / Telemetri)
| Kod | Ad | Açıklama |
|---|---|---|
| _TBD_ | | `[ÖNERİ]` ACK/NACK, INFO, PARAM, EVENT, STATUS, LOG |

## 4. Parametre Tablosu
_Detaylandırılacak — 04 §4.5 ile senkron tutulacak._

## 5. Akış Örnekleri (Sequence)
_Detaylandırılacak (bağlanma, senaryo başlatma, olay akışı, hata durumu)._

## 6. Hata Yönetimi
_Detaylandırılacak (CRC hatası, zaman aşımı, yeniden deneme, bilinmeyen komut)._

## 7. Sürümleme
_Detaylandırılacak (protokol sürümü GET_INFO ile bildirilir `[ÖNERİ]`)._
