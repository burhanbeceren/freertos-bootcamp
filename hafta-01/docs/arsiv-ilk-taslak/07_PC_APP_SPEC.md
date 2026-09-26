# 07 — PC Uygulaması Spesifikasyonu

| Sürüm | Tarih | Durum |
|---|---|---|
| v0.1 | 2026-09-26 | Taslak |

## 1. Teknoloji
| Bileşen | Seçim |
|---|---|
| Dil | Python 3.11+ |
| GUI | PySide6 |
| Grafik | pyqtgraph |
| Seri port | pyserial |
| Veri | numpy (istatistik), pandas (opsiyonel, analiz) |
| Paketleme | `requirements.txt`; ileride PyInstaller (opsiyonel) |

## 2. Modül Yapısı
```
pc_app/src/
├── main.py
├── link/serial_link.py      # Port listeleme, bağlanma, okuma thread'i
├── protocol/codec.py        # 06_PROTOCOL_SPEC uygulaması
├── protocol/commands.py     # Yüksek seviye komut API'si
├── model/event.py           # Olay veri modeli
├── model/session.py         # Oturum + istatistikler
├── model/scenario.py        # Senaryo/parametre modeli
├── storage/export.py        # CSV / JSON
└── ui/
    ├── main_window.py
    ├── connection_panel.py
    ├── scenario_panel.py
    ├── live_view.py
    ├── stats_panel.py
    └── health_panel.py
```

Seri okuma ayrı bir iş parçacığında yapılır; GUI'ye Qt sinyalleriyle aktarılır (GUI donmaz).

## 3. Ekranlar
```
┌──────────────────────────────────────────────────────────────────────┐
│ [Port: COM5 ▼] [Baud ▼] [Bağlan]   ● Bağlı  FW v0.1  Proto v1        │
├──────────────────┬───────────────────────────────────────────────────┤
│ SENARYO          │  CANLI GECİKME (µs) — zaman serisi                │
│ Profil: [S2 ▼]   │                                                   │
│ ─ CPU yükü ─     ├───────────────────────────┬───────────────────────┤
│ H: [x] p=5 ...   │  HİSTOGRAM                │ AŞAMA DÖKÜMÜ          │
│ ─ Kesme yükü ─   │                           │ (yığılmış çubuk)      │
│ f=[10 kHz] ...   │                           │                       │
│ ─ Kritik bölge ─ ├───────────────────────────┴───────────────────────┤
│ ...              │  İSTATİSTİK: n  min  max  ort  std  p50 p95 p99   │
│ [Uygula][Başlat] ├───────────────────────────────────────────────────┤
│ [Durdur][Sıfırla]│  SAĞLIK: CPU %  | Heap | Stack HWM | Kayıp olay   │
├──────────────────┴───────────────────────────────────────────────────┤
│ [Oturumu Kaydet] [Oturum Yükle] [Karşılaştır]         Log penceresi  │
└──────────────────────────────────────────────────────────────────────┘
```

| Panel | İlgili gereksinim |
|---|---|
| Bağlantı | FR-040 |
| Senaryo / parametre | FR-041, FR-024, FR-025 |
| Canlı grafik + histogram | FR-042 |
| Aşama dökümü | FR-043 |
| İstatistik | FR-044 |
| Kaydet / yükle | FR-045 |
| Sağlık | FR-046 |

## 4. Oturum Karşılaştırma
- Birden fazla oturum aynı histogram / kutu grafiği (box plot) üzerinde üst üste gösterilebilir.
- Amaç: senaryolar arası gecikme farkını tek bakışta göstermek.

## 5. Veri Kaydı Formatı
- **CSV:** Her satır bir olay (ham damgalar + türetilmiş metrikler).
- **JSON (meta):** Oturum başlığı — tarih, FW sürümü/hash, derleme profili, saat ayarları, senaryo parametrelerinin tam dökümü, istatistik özeti.
- Dosya adı: `results/<YYYYMMDD_HHMMSS>_<senaryo>.{csv,json}`.

## 6. Açık Konular
- Birim gösterimi (µs / çevrim) seçilebilir mi?
- Otomatik tekrar modu (ileride kart kendi kendini tetiklerse) — kapsam dışı, bkz. ADR-004.
