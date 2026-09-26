# 01 — Sistem Gereksinimleri

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Amaç
FreeRTOS çalıştıran bir STM32F407 sisteminde, kullanıcı butonuna basılmasından sistemin yanıt vermesine kadar geçen süreyi **farklı yük koşulları altında** ölçmek, istatistiksel olarak raporlamak ve gecikmenin **hangi aşamadan kaynaklandığını** açıklamak.

## 2. Kapsam
### 2.1 Kapsam İçi
- FreeRTOS tabanlı firmware (görevler, ISR, senkronizasyon).
- Buton olayının yakalanması ve bir "yanıt" aksiyonunun üretilmesi.
- DWT CYCCNT ile aşamalı zaman damgası alınması.
- Yapılandırılabilir yapay yük üreteçleri (CPU, kesme, kritik bölge, iletişim).
- USART üzerinden PC ile çift yönlü iletişim (komut + telemetri).
- PC arayüzünde senaryo kontrolü, canlı gösterim, kayıt ve dışa aktarma.

### 2.2 Kapsam Dışı (bu faz için)
- Harici ölçüm cihazıyla (lojik analizör/osiloskop) doğrulama — bkz. ADR-004.
- Edge AI modelinin çalıştırılması (ileriki faz; mimari buna açık tutulacak).
- Güç tüketimi ölçümü, düşük güç modları.

## 3. Paydaşlar ve Kullanım Senaryoları
| ID | Senaryo |
|---|---|
| UC-01 | Kullanıcı yük yokken butona basar, PC'de gecikme dökümünü görür. |
| UC-02 | Kullanıcı PC'den bir yük senaryosu seçer, butona tekrar tekrar basar, dağılımı karşılaştırır. |
| UC-03 | Kullanıcı görev önceliklerini/parametreleri PC'den değiştirir, etkisini gözlemler. |
| UC-04 | Kullanıcı bir deney oturumunu CSV/JSON olarak kaydeder ve sonra analiz eder. |
| UC-05 | Kullanıcı sistemin sağlık durumunu (CPU yükü, stack, heap, kayıp olay) izler. |

## 4. Sözlük
| Terim | Tanım |
|---|---|
| Olay (event) | Tek bir buton basışı ve onunla ilişkili tüm zaman damgaları. |
| Yanıt (response) | Buton olayına karşılık sistemin ürettiği gözlemlenebilir aksiyon (ör. LED/GPIO set). Kesin tanımı: 05_MEASUREMENT_SPEC. |
| Uçtan uca gecikme | Olayın firmware tarafından ilk yakalandığı an ile yanıtın üretildiği an arasındaki süre. |
| Aşama gecikmesi | Uçtan uca gecikmeyi oluşturan alt aralıklar (ISR, zamanlayıcı, işleme, …). |
| Yük senaryosu | Ölçüm sırasında aktif olan yük üreteçleri ve parametrelerinin bütünü. |
| Oturum (session) | Aynı senaryo altında toplanan olaylar kümesi. |
| Jitter | Gecikme dağılımının yayılımı (TBD: tanım — std, p99−p50, max−min). |

## 5. Fonksiyonel Gereksinimler

### 5.1 Olay Yakalama ve Yanıt
| ID | Gereksinim |
|---|---|
| FR-001 | Sistem, kullanıcı butonu (B1/PA0) basışını harici kesme (EXTI) ile yakalamalıdır. |
| FR-002 | Buton sıçraması (bounce) aynı basış için birden fazla olay üretmemelidir; debounce yöntemi ölçümü bozmayacak şekilde tasarlanmalıdır. |
| FR-003 | Her basış için ISR'den bir FreeRTOS görevine bildirim yapılmalı, yanıt bu görevde üretilmelidir. |
| FR-004 | Yanıt, gözlemlenebilir bir aksiyon (LED + test GPIO) olmalıdır. |
| FR-005 | ISR→görev bildirim mekanizması yapılandırılabilir olmalıdır (task notification / binary semaphore / queue) — karşılaştırma amaçlı. |

### 5.2 Ölçüm
| ID | Gereksinim |
|---|---|
| FR-010 | Her olay için tanımlı zaman damgası noktalarında DWT CYCCNT değeri kaydedilmelidir. |
| FR-011 | Uçtan uca ve aşama gecikmeleri çevrim ve µs cinsinden hesaplanabilmelidir. |
| FR-012 | Ölçüm altyapısının kendi getirdiği ek yük (overhead) ölçülmeli ve raporlanmalıdır. |
| FR-013 | Olaylar sıra numarası taşımalı; kaybolan/üst üste binen olaylar tespit edilmelidir. |
| FR-014 | Her olay kaydına o anki senaryo kimliği ve sistem bağlamı (aktif görev, CPU yükü vb. — TBD) eklenmelidir. |

### 5.3 Yük Üretimi
| ID | Gereksinim |
|---|---|
| FR-020 | Sistem, ayarlanabilir önceliğe ve görev döngüsüne (duty) sahip CPU yük görevleri sunmalıdır. |
| FR-021 | Sistem, ayarlanabilir frekans ve süreye sahip periyodik kesme yükü sunmalıdır. |
| FR-022 | Sistem, ayarlanabilir uzunlukta kritik bölge (kesmeler kapalı / scheduler askıda) yükü sunmalıdır. |
| FR-023 | Sistem, iletişim kaynaklı yükü (yoğun telemetri) açıp kapatabilmelidir. |
| FR-024 | Yük senaryoları çalışma anında, yeniden derleme gerektirmeden PC'den değiştirilebilmelidir. |
| FR-025 | Önceden tanımlı senaryo profilleri bulunmalıdır (ör. S0: yüksüz … Sn). |

### 5.4 İletişim ve Kontrol
| ID | Gereksinim |
|---|---|
| FR-030 | MCU ile PC arasında USART2 üzerinden çift yönlü, çerçeveli ve hata denetimli bir protokol kullanılmalıdır. |
| FR-031 | PC; senaryo başlatma/durdurma, parametre okuma/yazma, ölçüm sıfırlama komutları gönderebilmelidir. |
| FR-032 | MCU; olay kayıtlarını, periyodik sistem durumunu ve komut yanıtlarını gönderebilmelidir. |
| FR-033 | Telemetri gönderimi, ölçülen yanıt yolunu engellememelidir (bloklamayan, tamponlu). |

### 5.5 PC Arayüzü
| ID | Gereksinim |
|---|---|
| FR-040 | Seri port seçimi, bağlantı ve bağlantı durumu gösterimi. |
| FR-041 | Senaryo seçimi ve parametre düzenleme paneli. |
| FR-042 | Canlı gecikme grafiği (zaman serisi) ve histogram. |
| FR-043 | Aşama bazlı gecikme dökümü (yığılmış çubuk). |
| FR-044 | İstatistik tablosu: n, min, max, ortalama, std, p50, p95, p99. |
| FR-045 | Oturumların CSV/JSON olarak kaydı ve tekrar yüklenmesi. |
| FR-046 | Sistem sağlık paneli: CPU yükü, görev stack high-water mark, serbest heap, kayıp olay sayısı. |

## 6. Fonksiyonel Olmayan Gereksinimler
| ID | Gereksinim |
|---|---|
| NFR-001 | Zaman çözünürlüğü: 1 CPU çevrimi (168 MHz'de ≈ 5,95 ns). |
| NFR-002 | Ölçüm overhead'i, yüksüz uçtan uca gecikmenin %5'inden az olmalıdır (hedef, TBD-05). |
| NFR-003 | CYCCNT taşması (≈ 25,6 s) aralık hesaplarını bozmamalıdır (işaretsiz fark aritmetiği). |
| NFR-004 | Ölçüm tekrarlanabilir olmalıdır: aynı senaryo + firmware ile istatistikler tutarlı kalmalıdır. |
| NFR-005 | Firmware'de dinamik bellek yalnızca başlangıçta ayrılmalıdır (çalışma anında malloc yok). |
| NFR-006 | `configASSERT`, stack overflow kontrolü ve malloc failed hook etkin olmalıdır. |
| NFR-007 | Kod, uygulama katmanını (App/) CubeMX üretimli koddan ayırmalıdır. |
| NFR-008 | PC uygulaması Windows 11 üzerinde Python 3.11+ ile çalışmalıdır. |
| NFR-009 | Mimari, ileride bir Edge AI çıkarım görevinin "gerçekçi yük" olarak eklenmesine uygun olmalıdır. |

## 7. Kısıtlar ve Varsayımlar
- Harici ölçüm cihazı kullanılmayacak; fiziksel basış → EXTI arası (buton mekaniği, RC filtre, senkronizasyon) **doğrudan ölçülemez**, yalnızca teorik olarak açıklanır.
- Cortex-M4 kesme girişi gecikmesi (≈12 çevrim + flash bekleme durumları) iç ölçümle doğrudan görülemez; ISR'nin ilk komutunda alınan damga "t0" kabul edilir.
- DISC1 kartında ST-LINK sanal COM portu yoktur; harici USB-TTL gerekir.

## 8. Açık Konular (TBD)
| ID | Konu | Sahip | Hedef doküman |
|---|---|---|---|
| TBD-01 | Zaman damgası noktalarının kesin tanımı | Kullanıcı | 05 |
| TBD-02 | "Yanıt" aksiyonunun kesin tanımı | Kullanıcı | 05 |
| TBD-03 | Debounce yöntemi ve ölçümle etkileşimi | Kullanıcı | 04 / 05 |
| TBD-04 | Protokol çerçeve formatı, komut seti, baud hızı | Kullanıcı | 06 |
| TBD-05 | Kabul kriterleri (overhead, jitter limitleri) | Kullanıcı | 05 / 08 |
| TBD-06 | Jitter tanımı | Kullanıcı | 05 |
| TBD-07 | Olay kaydına eklenecek sistem bağlamı alanları | Kullanıcı | 05 / 06 |
| TBD-08 | Senaryo profillerinin listesi ve parametreleri | Birlikte | 04 / 08 |
| TBD-09 | CPU yükü ölçüm yöntemi (idle hook sayacı vs. run-time stats) | Birlikte | 04 |
