<!-- analysis/scripts/analyze.py tarafından gerçek ölçümden üretilir. Elle düzenlemeyin. -->

| Senaryo | Olay | Seçim | t1−t0 | t2−t1 | t3−t2 | t4−t3 | **R** | **Pay (20 − R)** | Sonuç |
|---|---|---|---|---|---|---|---|---|---|
| S0 | 9 | en iyi gözlenen | 0.006 | 0.007 | 0.019 | 5.550 | **5.582** | **+14.418** | ✅ karşılandı |
| S3 | 7 | en iyi gözlenen | 0.006 | 0.007 | 0.019 | 5.550 | **5.582** | **+14.418** | ✅ karşılandı |
| S3 | 11 | en kötü gözlenen | 0.024 | 0.007 | 5.582 | 5.554 | **11.167** | **+8.833** | ✅ karşılandı |
| S5 | 1 | en iyi gözlenen | 4.914 | 0.006 | 9.996 | 5.551 | **20.467** | **-0.467** | ❌ kaçırıldı |
| S5 | 10 | ortanca | 0.007 | 0.006 | 98.833 | 5.552 | **104.398** | **-84.398** | ❌ kaçırıldı |
| S5 | 30 | en kötü gözlenen | 0.006 | 0.007 | 159.596 | 5.550 | **165.159** | **-145.159** | ❌ kaçırıldı |

Süreler ms'dir. Olaylar ham CSV'den seçilir: her senaryonun en iyi, ortanca ve en kötü gözlenen `ok` olayı (R'si 50 µs'den yakın olanlar tekrar gösterilmez).
