# Yol Haritası ve Öneriler

## Durum

| Adım | Durum |
|---|---|
| Gereksinim, zaman çizelgesi, hipotez planı | ✅ |
| Firmware: 3 görev, t₀…t₄, DMA/TC, DUMP; sıfır uyarıyla derleniyor | ✅ |
| PC arayüzü: port, TEL/BTN ayrımı, "Butona basıldı", CSV, grafik | ✅ |
| Analiz betikleri ve model | ✅ |
| **Kartta S0–S5 ölçümü (≥ 30 × 6)** | ⏳ Kullanıcı |
| `report.md` yorumları | ⏳ Ölçüm sonrası |
| Video: çalışan sistem ve senaryo farkları | ⏳ Kullanıcı |

## Öneriler (çekirdek deney standardını DEĞİŞTİRMEYEN ek deneyler)

S0–S5 karşılaştırması sabit kalır. Aşağıdakiler ayrı `Sx-ext` deneyleri olarak raporlanmalıdır.

1. **H3 ayırıcı deneyi, öncelik tersine çevirme:** UartTxTask'ı öncelik 3'e alıp S5'i tekrarlayın. Birikme kaybolursa darboğazın UART hattı değil, TX görevinin CPU açlığı olduğu kanıtlanır.
2. **Öncelikli kuyruk:** BTN mesajlarını `xQueueSendToFront` ile kuyruğun önüne koyun. S3'teki t₃−t₂ bekleme süresini (≤ 5,6 ms) sıfıra yaklaştırması beklenir. Ancak hattaki mesaj kesilemediği için alt sınır yine L olur.
3. **Baud artırma:** 921600 baud ile hat süresi 5,56 ms'den 0,69 ms'ye iner. R'nin taban değeri ve S5 kararsızlık eşiği (C* ≈ T − L) değişir. Model bunu önceden tahmin edebilir.
4. **Harici doğrulama:** PE7–PE10 pinlerinden birinde ISR girişi ve TC anında pin toggle ederek lojik analizörle t₀ ve t₄ doğrulanabilir. Ayrıca fiziksel basış → t₀ aralığı da ölçülebilir.
5. **SEGGER SystemView / Tracealyzer:** Görev geçişlerinin gerçek zaman çizelgesi elde edilir ve modelin çizelgesiyle yan yana konabilir.
6. **Otomatik uyarım:** İkinci bir GPIO'yu PA0'a bağlayıp (loopback) binlerce "basış" üretmek. p99 değerleri anlamlı hale gelir; insan zamanlaması ortadan kalkar.
7. **CPU yükü ölçümü:** Idle hook sayacı veya `configGENERATE_RUN_TIME_STATS` ile her senaryonun gerçek CPU kullanımı raporlanabilir.
8. **CI:** GitHub Actions ile her push'ta firmware derlemesi (arm-none-eabi-gcc) ve pytest çalıştırılabilir.
9. **Edge AI hazırlığı:** S4/S5'teki sentetik CPU işinin yerine küçük bir CMSIS-NN / TFLite Micro çıkarımı konarak "gerçekçi yük" altında aynı ölçüm yapılabilir.
