# Ölçümler (ham veri)

> 🟡 **Henüz gerçek kart ölçümü yok.** Bu klasöre yalnızca STM32F407G-DISC1 üzerinde yapılan deneylerin çıktıları konur. Sentetik veya model verisi buraya **konmaz**.

Dosyaları arayüz (`python -m uart_monitor`) ve analiz betiği üretir:

| Dosya | Üreten | İçerik |
|---|---|---|
| `S0.csv … S5.csv` | Arayüz (DUMP) | Her satır bir buton olayı: `scenario,event_id,t0_us,t1_us,t2_us,t3_us,t4_us,status` |
| `Sx_counters.csv` | Arayüz (DUMP + INFO) | MCU sayaçları: kayıplar, hatalar, gerçek TEL periyodu, gerçek CPU işi, stack/heap |
| `raw/Sx_session.log` | Arayüz | Ham UART dökümü. PC zamanı yalnız bilgi amaçlıdır; faz analizi MCU zamanlı TEL satırlarından yapılır. |
| `summary.csv` | `analysis/scripts/analyze.py` | Senaryo başına özet |

Kurallar:
- Zamanlar MCU TIM2 µs'dir. Farklar mod 2³² hesaplanır.
- Eksik zaman boş bırakılır; 0 yazılmaz.
- Durumlar: `ok`, `btn_drop`, `tx_drop`, `tx_error`, `timeout`.
