# Rapor — Yük Altında Buton Yanıt Süresi (Gerçek Kart Ölçümleri)

> 🟡 **DURUM: ÖLÇÜM BEKLENİYOR.** Bu dosyada henüz gerçek kart verisi yok. Sentetik veya model verisi burada sonuç olarak **sunulmaz**. Ölçüm tamamlanınca §2–§5 doldurulacak.

| | |
|---|---|
| Kart | STM32F407G-DISC1 |
| Firmware | `INF,fw` / `INF,git` / `INF,build` → _ölçümden sonra doldurulacak_ |
| Ölçüm tarihi | _…_ |
| Ham veri | [../measurements/](../measurements/) |
| Özet | `../measurements/summary.csv` (ölçümden sonra `analyze.py` üretir) |
| Grafik kodu | [scripts/analyze.py](scripts/analyze.py) |
| Hipotezler | [analiz.md](analiz.md) |

## 1. Yöntem (özet)
Deney koşulları: [../docs/gereksinim.md](../docs/gereksinim.md) §4–§6. Zaman damgaları TIM2'den (1 MHz) alınır. Farklar mod 2³² hesaplanır. Yalnızca `status=ok` olan olaylar R istatistiğine girer. Diğer olaylar ayrı sayılır ve "deadline karşılandı" kapsamına alınmaz.

## 2. Sonuç tabloları
Tablolar `analysis/results_tables.md` dosyasından alınır. Bu dosyayı `python analysis/scripts/analyze.py` üretir.

_Ölçüm sonrası: results_tables.md içeriği buraya yapıştırılacak veya bağlantı verilecek._

## 3. Grafikler

| Grafik | Dosya |
|---|---|
| Olay numarası → R, 20 ms çizgisi | `plots/R_vs_event.png` |
| Senaryo → aşama ortalamaları (yığılmış) | `plots/stages_stacked.png` |
| Aşama dağılımları | `plots/stages_box.png` |
| R ve telemetri fazı | `plots/R_vs_phase.png` |

## 4. Hipotezlerin değerlendirmesi

Her satır şu soruları yanıtlar: Hangi bileşen değişti? Neden? Hangi ölçüm destekliyor? Ne henüz bilinmiyor?

| Hipotez | Karar (destek / red / test edilemedi) | Kanıt (tablo satırı, grafik) | Açıklama |
|---|---|---|---|
| H0: t₄−t₃ sabit | _…_ | | |
| H1: Frekans → yalnız t₃−t₂ | _…_ | | |
| H2: S4, t₁−t₀ ≤ 2 ms, birikme yok | _…_ | | |
| H3: S5, UartTxTask açlığı → birikme | _…_ | | |

## 5. Model ile karşılaştırma
S0'dan ölçülen ek yüklerle `rtos_model.Overheads` güncellenecek ve tahmin–ölçüm farkı tablolanacak.

## 6. Sınırlar
- t₀ fiziksel basış değildir. t₄'e TC kesmesinin gözlem gecikmesi dahildir.
- Gözlenen maksimum, kanıtlanmış worst-case değildir. n ≈ 30 ile uç yüzdelikler güvenilir değildir.
- _Ölçüm sırasında fark edilen sapmalar (ör. work_us, periyot) buraya._
