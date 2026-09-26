# Analiz Planı: Hipotezler ve Ölçüm Planı

> Bu doküman **ölçümden önce** yazıldı. Tahminler [../docs/zaman-cizelgesi.md](../docs/zaman-cizelgesi.md) içindeki modelden gelir. Gerçek sonuçlar ve hipotezlerin kabul/red kararı [report.md](report.md) içinde yer alır.

## 1. Soru

"100 Hz daha yavaş" demek yeterli değil. Asıl sorular şunlar:
- Gecikme **ne kadar** değişiyor?
- **Hangi koşulda** değişiyor?
- **Hangi aşamada** (t₁−t₀, t₂−t₁, t₃−t₂, t₄−t₃) değişiyor?
- **Neden** değişiyor?

## 2. Hipotezler

### H0: Donanım aşaması sabittir
t₄−t₃, bütün senaryolarda L + ε ≈ 5,56–5,60 ms'dir ve yükten etkilenmez. TC kesmesi bütün görevlerden önceliklidir; DMA CPU'dan bağımsız çalışır.

| | |
|---|---|
| **Destekler** | Her senaryoda t₄−t₃'ün yayılımı (maks − min) < 50 µs; ortanca 5,56–5,62 ms |
| **Yanlışlar** | t₄−t₃ yükle birlikte artıyor, ya da dağılım > 0,1 ms yayılıyor. Bu durum TC'nin geç gözlendiğini (kesme maskelenmesi) gösterir. |

### H1: Telemetri frekansı yalnızca "TX öncesi" aşamayı etkiler (S0 → S1 → S2 → S3)
Telemetri frekansı arttıkça yanıt süresi uzar. Ancak artış **yalnızca t₃−t₂**'de görülür: BTN, FIFO'da hatta olan TEL mesajının bitmesini bekler. t₁−t₀ ve t₂−t₁ değişmez, çünkü ButtonTask TelemetryTask'ın yalnızca ~20 µs'lik biçimlendirmesini bekler.

| Tahmin | S1 | S2 | S3 |
|---|---|---|---|
| Bekleme yaşayan basış oranı ≈ hat kullanımı | %5,6 | %27,8 | %55,6 |
| t₃−t₂ ortalama ≈ U × L/2 | 0,17 ms | 0,80 ms | 1,59 ms |
| t₃−t₂ maks ≤ L + ε | 5,6 ms | 5,6 ms | 5,6 ms |
| R maks ≈ 2L | 11,2 ms | 11,2 ms | 11,2 ms |

| | |
|---|---|
| **Destekler** | (a) S0→S3 arasında t₃−t₂ ortalaması, U ile orantılı biçimde artar. (b) t₃−t₂ hiçbir zaman ~5,6 ms'i aşmaz. (c) t₁−t₀ ve t₂−t₁ senaryolar arasında < 0,1 ms değişir. (d) Faz grafiğinde R, "son TEL'den bu yana geçen süre" 0'a yakınken en yüksektir ve L sonra 5,6 ms'e iner (testere dişi). |
| **Yanlışlar** | (a) t₁−t₀ frekansla anlamlı artıyor. Bu, ISR/görev tarafında beklenmedik bir yük (ör. UART kesmesi) olduğunu gösterir. (b) t₃−t₂ > 2L. Bu, birden fazla mesajın biriktiğini, yani FIFO modelinin eksik olduğunu gösterir. (c) Faz ile R arasında ilişki yok. |

### H2: Kararlı CPU yükü iki aşamayı uzatır ama deadline korunur (S3 → S4)
C = 2 ms'lik iş TelemetryTask'ta (öncelik 3) çalışır.
- İş sırasında gelen basışlarda (≈ %20) **t₁−t₀ en fazla ~2 ms** uzar.
- t₃−t₂ ortalaması artar: TEL mesajı işten sonra kuyruğa girer ve BTN'in önüne geçer.
- UartTxTask'ın hizmet kapasitesi yeterlidir (C + L < T): birikme olmaz.
- Tahmin: R maks ≈ 13,2 ms; bütün yanıtlar deadline'ı karşılar.

| | |
|---|---|
| **Destekler** | t₁−t₀ dağılımı iki kümeli (~0,01 ms ve 0–2 ms). R maks ≤ ~13,5 ms. `tx_drop` = 0. R, event_id ile artmaz. `work_max_us` ≈ 2000. |
| **Yanlışlar** | t₁−t₀ > 2,1 ms (CPU işi beklenenden uzun veya başka bir yük var), ya da R event_id ile birlikte artıyor (birikme). |

### H3: S5'te darboğaz UART hattı değil, UartTxTask'ın CPU açlığıdır (S4 → S5)
C = 5 ms, C + L + ε > T = 10 ms. Bu yüzden bir TEL'in TC'si, TelemetryTask'ın bir sonraki işinin içine düşer. En düşük öncelikli UartTxTask, periyot başına **yalnızca bir** mesaj başlatabilir.
- İlk basışta R = 10,7–20,6 ms; basışların ~%6'sı deadline'ı kaçırır.
- Sonraki her basış kuyrukta **kalıcı +1 mesaj** bırakır; R ≈ +10 ms/basış artar.
- ~15. basıştan sonra TX kuyruğu (16) dolar: `tx_drop` ve `tel_tx_drop` > 0, R ≈ 160 ms'de doyar.
- Artışın neredeyse tamamı **t₃−t₂**'dedir; t₁−t₀ ≤ 5 ms ile sınırlıdır.

Hat kullanımı yalnızca %55,6'dır. Yani "UART yetmiyor" açıklaması **yanlıştır**. Hipoteze göre hat zamanın bir kısmında boşta kalırken mesajlar kuyrukta bekler.

| | |
|---|---|
| **Destekler** | (a) R vs event_id grafiği merdiven biçimindedir, adım ≈ 10 ms. (b) `tx_drop` > 0 ve `tel_tx_drop` > 0. (c) t₃−t₂ büyür; t₁−t₀ ≤ ~5 ms kalır. (d) `work_min_us` ≳ 4400. |
| **Yanlışlar** | (a) R, event_id ile artmıyor ve kalıcı birikme yok. (b) `work_max_us` < ~4,4 ms ise eşik aşılmamıştır; bu durumda sonuç H3'ü **test etmez**, yalnızca S4 benzeri davranışı gösterir. (c) Birikme var ama t₁−t₀'da. Bu, ButtonTask'ın aç kaldığını gösterir ve modeli yanlışlar. |

**Ayırıcı kontrol:** Aynı deneyi UartTxTask'ın önceliği ButtonTask'ın üstüne alınarak tekrarlamak. Hipotez doğruysa birikme kaybolmalıdır. Bu, çekirdek standardı değiştiren bir **ek deneydir**; S0–S5 karşılaştırmasına katılmaz. Bkz. [öneriler](../docs/ROADMAP.md).

## 3. Ölçüm planı

| Ne | Nasıl | Dosya |
|---|---|---|
| Olay başına t₀…t₄ + durum | MCU RAM kaydı → `DUMP` → CSV | `measurements/Sx.csv` |
| Kayıp/hata sayaçları, gerçek TEL periyodu, gerçek CPU işi süresi | MCU sayaçları (`CNT`) | `measurements/Sx_counters.csv` |
| Faz analizi için TEL üretim anları (MCU saati) | Ham UART dökümü | `measurements/raw/Sx_session.log` |
| Özet tablo | `analysis/scripts/analyze.py` | `measurements/summary.csv` |

**Örneklem:** Her senaryoda ≥ 30 kabul edilen basış, aralarında ≥ 0,5 s ve düzensiz zamanlama. Basışlar düzensiz olduğu için telemetri fazı rastgele örneklenir.

**Grafikler** (hepsi ham CSV'den çizilir):
1. `R_vs_event.png`: olay numarası → R, 20 ms çizgisi, kayıplar işaretli. (H3 merdiveni burada görünür.)
2. `stages_stacked.png`: senaryo → aşama ortalamaları, yığılmış; model tahmini ◆ ile gösterilir.
3. `stages_box.png`: aşama dağılımları. Hangi aşama değişiyor sorusunun kanıtı.
4. `R_vs_phase.png`: R ve telemetri fazı. H1'in testere dişi burada görünür.

**Doğrulama:** Her senaryoda `CNT,tel_period_*` (10/20/100 ms), `CNT,work_*` (≈ 2000/5000 µs), `INF,msg_len = 64` kontrol edilir. Beklenen dışı bir değer, o senaryonun yorumunda belirtilir.

## 4. Bilinmeyenler ve ölçüm sınırları
- t₀ fiziksel basma anı değildir; buton mekaniği ve RC filtre ölçülmez.
- t₄, TC kesmesinin **gözlendiği** andır; kesme gecikmesi (< birkaç µs) dahildir.
- 30 örnekle p99 anlamlı değildir; "gözlenen maksimum" kanıtlanmış worst-case değildir.
- Modeldeki ek yükler varsayımdır. S0 ölçümü t₁−t₀, t₂−t₁, t₃−t₂ ve t₄−t₃−L için gerçek değerleri verir; model bu değerlerle yeniden çalıştırılmalıdır.
