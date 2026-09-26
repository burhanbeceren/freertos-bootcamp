# 08 — Test ve Doğrulama Planı

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Test Seviyeleri
| Seviye | Kapsam | Yöntem |
|---|---|---|
| Birim (PC) | codec, istatistik, export | pytest |
| Birim (FW) | ring buffer, config doğrulama, CRC | Host üzerinde derlenen C testleri (opsiyonel, Unity) |
| Entegrasyon | PC ↔ MCU protokolü | Loopback + gerçek kart |
| Sistem | Uçtan uca ölçüm, senaryolar | Deney matrisi (§3) |

## 2. Doğrulama Testleri (ölçüm altyapısının kendisi)
| ID | Test | Beklenen |
|---|---|---|
| VT-01 | DWT sayacı çalışıyor mu? `HAL_Delay(1000)` öncesi/sonrası fark | ≈168 000 000 çevrim (±tick hassasiyeti) |
| VT-02 | Boş ölçüm overhead'i (ardışık iki `dwt_now()`) | Sabit ve birkaç çevrim |
| VT-03 | Bilinen meşgul döngü (ör. 100 µs) ölçümü | 100 µs ± overhead |
| VT-04 | CYCCNT taşması sırasında olay | Doğru fark, hata yok |
| VT-05 | Buton sıçraması: 100 basış | 100 olay (fazlası/eksiği yok) |
| VT-06 | Ring buffer taşması (telemetri durdurulmuş) | `dropped_events` doğru artar, sistem çökmez |
| VT-07 | Sağlık: 1 saat çalışma | Stack overflow yok, heap sabit, assert yok |

## 3. Deney Matrisi (senaryolar — TBD-08)
Her senaryo için en az **N = 100** basış (TBD).

| Senaryo | Açıklama | Hipotez (bkz. 02 §2) |
|---|---|---|
| S0 | Yük yok (referans) | Taban çizgisi |
| S1 | Düşük öncelikli CPU yükü %90 | S0 ile aynı |
| S2 | Eş öncelikli CPU yükü | Gecikme ≤ 1 tick artar |
| S3 | Yüksek öncelikli CPU yükü | Gecikme ≈ yük süresi kadar artar |
| S4 | Periyodik kesme yükü (API sınırının altında öncelik) | ISR/görev aşamaları artar |
| S5 | Kritik bölge (`taskENTER_CRITICAL`) | ISR girişi gecikir |
| S6 | `vTaskSuspendAll` | Görev aşaması gecikir, ISR etkilenmez |
| S7 | Yoğun telemetri | Hafif artış |
| S8 | Bildirim mekanizması karşılaştırması (notify / semaphore / queue) | notify en hızlı |
| S9 | Karma yük | — |

## 4. Raporlama
Her deney için:
- Senaryo parametreleri, FW sürümü, derleme profili (JSON meta).
- İstatistik tablosu, histogram, aşama dökümü.
- Hipotezle karşılaştırma ve gecikme kaynağının açıklaması.

## 5. Kabul Kriterleri
_05_MEASUREMENT_SPEC §9 kesinleştiğinde doldurulacak (TBD-05)._
