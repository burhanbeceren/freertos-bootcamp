# Yol Haritası ve Öneriler

## Durum

| Adım | Durum |
|---|---|
| Gereksinim, zaman çizelgesi, hipotez planı | ✅ |
| Firmware: 3 görev, t₀…t₄, DMA/TC, DUMP; sıfır uyarıyla derleniyor | ✅ |
| PC arayüzü: port, TEL/BTN ayrımı, "Butona basıldı", CSV, grafik | ✅ |
| Analiz betikleri (gerçek veriden grafik + zaman çizelgesi) | ✅ |
| Kartta S0–S5 ölçümü (30 × 6 = 180 olay) | ✅ |
| `report.md`: gerçek veriyle analiz ve hipotez kararları | ✅ |
| İyileştirme: A/B/C varyantları, EXTI enjeksiyonu, ST-LINK komut kanalı, yeni arayüz | ✅ (FW 1.1.0) |
| 18 varyant deneyi (A/B/C × S0–S5, INJ, 50'şer olay) | ✅ |

## Öneriler (çekirdek deney standardını DEĞİŞTİRMEYEN ek deneyler)

S0–S5 karşılaştırması sabit kalır. Aşağıdakiler ayrı `Sx-ext` deneyleri olarak raporlanmalıdır.

1. ~~Öncelik tersine çevirme~~ ve ~~öncelikli kuyruk~~ → **varyant C ve B olarak uygulandı** (ADR-011).
2. **B/C'yi fiziksel butonla da ölçmek** (`runs/B-HW`, `runs/C-HW`): enjeksiyonla aynı sonucu vermesi beklenir.
3. **Baud artırma:** 921600 baud ile hat süresi 5,56 ms'den 0,69 ms'ye iner. R'nin taban değeri ve S5 kararsızlık eşiği (C* ≈ T − L) değişir.
4. **SEGGER SystemView / Tracealyzer:** Görev geçişlerinin gerçek zaman çizelgesi elde edilir (ST-LINK üzerinden, ek donanım gerekmez).
5. ~~Otomatik uyarım~~ → **EXTI enjeksiyonu olarak uygulandı** (ADR-012). Olay sayısı 128'e kadar artırılabilir.
6. **CPU yükü ölçümü:** Idle hook sayacı veya `configGENERATE_RUN_TIME_STATS` ile her senaryonun gerçek CPU kullanımı raporlanabilir.
7. **CI:** GitHub Actions ile her push'ta firmware derlemesi (arm-none-eabi-gcc) ve pytest çalıştırılabilir.
8. **Edge AI hazırlığı:** S4/S5'teki yapay CPU işinin yerine küçük bir CMSIS-NN / TFLite Micro çıkarımı konarak "gerçekçi yük" altında aynı ölçüm yapılabilir.
