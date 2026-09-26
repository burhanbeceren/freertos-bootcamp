# Yol Haritası

| Faz | Hedef | Çıktı | Durum |
|---|---|---|---|
| F0 | Spesifikasyon | `docs/` seti; 05 ve 06 detaylandırılmış | **Devam ediyor** |
| F1 | Temel firmware | CubeMX projesi, 168 MHz, FreeRTOS, heartbeat LED, USART2 echo | Bekliyor |
| F2 | Ölçüm çekirdeği | EXTI → ResponseTask, DWT damgaları, ring buffer, VT-01…VT-05 | Bekliyor |
| F3 | Protokol + PC iskeleti | Codec (FW + PC), bağlantı paneli, ham olay listesi | Bekliyor |
| F4 | Yük üreteçleri | CPU / kesme / kritik bölge / iletişim yükleri, config deposu | Bekliyor |
| F5 | PC arayüzü tam | Grafikler, istatistik, senaryo paneli, kayıt/yükleme, karşılaştırma | Bekliyor |
| F6 | Deneyler ve rapor | S0…S9 deney matrisi, gecikme kaynağı analizi | Bekliyor |
| F7 | Edge AI hazırlığı | Çıkarım görevini yük üreteci olarak ekleme (ör. TFLite Micro / CMSIS-NN) | Gelecek |

## F0 için sıradaki adımlar
- [ ] 05_MEASUREMENT_SPEC: damga noktaları, yanıt tanımı, metrikler, jitter, kabul kriterleri
- [ ] 06_PROTOCOL_SPEC: çerçeve formatı, komut seti, parametre tablosu, hata yönetimi
- [ ] TBD-03 debounce kararı
- [ ] TBD-08 senaryo profilleri
- [ ] TBD-09 CPU yükü ölçüm yöntemi
