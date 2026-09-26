"""Arayüzün "Ölçümler" ve "Analiz" sekmeleri.

Her iki sekme de yalnızca diske kaydedilmiş GERÇEK ham veriyi (measurements/Sx.csv)
okur. Grafikler analysis/scripts/analyze.py ile aynı koddan üretilir; arayüz ile
depodaki grafikler bu yüzden birebir aynıdır.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .metrics import DEADLINE_US, STAGES, read_counters, read_csv

HAFTA_ROOT = Path(__file__).resolve().parents[2]
ANALYZE_PY = HAFTA_ROOT / "analysis" / "scripts" / "analyze.py"
SCENARIOS = ["S0", "S1", "S2", "S3", "S4", "S5"]


def _load_analyze():
    spec = importlib.util.spec_from_file_location("hafta01_analyze", ANALYZE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fill(table: QTableWidget, headers: list, rows: list, colors: dict | None = None):
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            it = QTableWidgetItem("" if v is None else str(v))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if j else Qt.AlignLeft | Qt.AlignVCenter)
            if colors and i in colors:
                it.setForeground(colors[i])
            table.setItem(i, j, it)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)


def _ms(us):
    return "" if us is None else f"{us / 1000:.3f}"


class MeasurementsView(QWidget):
    """Kaydedilmiş bir senaryonun olay tablosu ve MCU sayaçları."""

    def __init__(self, out_dir_getter):
        super().__init__()
        self._out_dir = out_dir_getter
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.scn = QComboBox()
        self.scn.addItems(SCENARIOS)
        self.scn.currentTextChanged.connect(self.refresh)
        self.info = QLabel("")
        self.info.setStyleSheet("color: gray")
        top.addWidget(QLabel("Senaryo:"))
        top.addWidget(self.scn)
        top.addWidget(QPushButton("↻ Yenile", clicked=self.refresh))
        top.addStretch(1)
        top.addWidget(self.info)
        v.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.events = QTableWidget()
        self.counters = QTableWidget()
        split.addWidget(self.events)
        split.addWidget(self.counters)
        split.setSizes([800, 300])
        v.addWidget(split, 1)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        v.addWidget(self.summary)

    def show_scenario(self, name: str):
        if self.scn.currentText() != name:
            self.scn.setCurrentText(name)
        else:
            self.refresh()

    def refresh(self):
        name = self.scn.currentText()
        mdir = Path(self._out_dir())
        path = mdir / f"{name}.csv"
        if not path.exists():
            self.events.clear()
            self.events.setRowCount(0)
            self.counters.clear()
            self.counters.setRowCount(0)
            self.info.setText(f"{path} yok")
            self.summary.setText("Bu senaryo henüz kaydedilmedi.")
            return
        rows = read_csv(path)
        table, colors = [], {}
        from PySide6.QtGui import QColor
        for i, r in enumerate(rows):
            R = r.response_us
            margin = None if R is None else DEADLINE_US - R
            table.append([r.event_id, r.status] + [_ms(r.stage_us(a, b)) for _, a, b, _ in STAGES]
                         + [_ms(R), _ms(margin)])
            if r.status != "ok":
                colors[i] = QColor("#dc2626")
            elif R > DEADLINE_US:
                colors[i] = QColor("#b45309")
        _fill(self.events, ["event_id", "durum"] + [f"{lab} (ms)" for lab, *_ in STAGES]
              + ["R (ms)", "pay (ms)"], table, colors)

        cnt = read_counters(mdir / f"{name}_counters.csv")
        _fill(self.counters, ["anahtar", "değer"], [[k, v] for k, v in cnt.items()])
        self.info.setText(str(path))

        ok = [r.response_us for r in rows if r.status == "ok" and r.response_us is not None]
        late = sum(1 for x in ok if x > DEADLINE_US)
        lost = len(rows) - len(ok)
        if ok:
            self.summary.setText(
                f"<b>{name}</b>: {len(rows)} olay · ok {len(ok)} · deadline karşılandı "
                f"{len(ok) - late} · 20 ms'yi aşan {late} · kayıp/hata {lost} · "
                f"R min/ort/maks = {min(ok) / 1000:.3f} / {sum(ok) / len(ok) / 1000:.3f} / "
                f"{max(ok) / 1000:.3f} ms · min pay {(DEADLINE_US - max(ok)) / 1000:+.3f} ms  "
                f"<span style='color:#dc2626'>(kırmızı: kayıp)</span> "
                f"<span style='color:#b45309'>(turuncu: geç)</span>")
        else:
            self.summary.setText(f"{name}: tamamlanmış yanıt yok.")


class AnalysisView(QWidget):
    """Ham CSV → özet tablo + grafikler (analyze.py ile aynı çıktı)."""

    IMAGES = [
        ("Olay → R (20 ms çizgisi)", "analysis/plots/R_vs_event.png"),
        ("Aşama ortalamaları (yığılmış)", "analysis/plots/stages_stacked.png"),
        ("Aşama dağılımları", "analysis/plots/stages_box.png"),
        ("R – telemetri fazı", "analysis/plots/R_vs_phase.png"),
        ("Zaman çizelgesi S0/S3/S5", "docs/zaman-cizelgesi.png"),
    ]

    def __init__(self, out_dir_getter):
        super().__init__()
        self._out_dir = out_dir_getter
        self._pix: QPixmap | None = None
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.run_btn = QPushButton("▶ Analizi çalıştır (ham CSV → tablo + grafikler)", clicked=self.run)
        self.status = QLabel("")
        self.status.setStyleSheet("color: gray")
        top.addWidget(self.run_btn)
        top.addWidget(self.status, 1)
        v.addLayout(top)

        self.table = QTableWidget()
        self.table.setMaximumHeight(230)
        v.addWidget(self.table)

        sel = QHBoxLayout()
        self.img_cb = QComboBox()
        for title, _ in self.IMAGES:
            self.img_cb.addItem(title)
        self.img_cb.currentIndexChanged.connect(self.show_image)
        sel.addWidget(QLabel("Grafik:"))
        sel.addWidget(self.img_cb, 1)
        v.addLayout(sel)

        self.img = QLabel("Analizi çalıştırın.")
        self.img.setAlignment(Qt.AlignCenter)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.img)
        v.addWidget(self.scroll, 1)

    def run(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            mod = _load_analyze()
            res = mod.run_analysis(measurements=Path(self._out_dir()))
        except Exception as exc:  # grafik/okuma hatası arayüzü düşürmesin
            self.status.setText(f"Hata: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        rows = res["rows"]
        if not rows:
            self.status.setText("Ölçüm bulunamadı. Önce en az bir senaryoyu kaydedin.")
            return

        def f(v, d=2):
            return "" if v in (None, "") else (f"{v:.{d}f}" if isinstance(v, float) else str(v))

        table = [[r["scenario"], r["n_events"], r["n_ok"], r["n_met"], r["n_late"],
                  r["n_btn_drop"] + r["n_tx_drop"] + r["n_tx_error"] + r["n_timeout"],
                  f(r["R_min_ms"]), f(r["R_mean_ms"]), f(r["R_max_ms"]), f(r["margin_min_ms"]),
                  f(r["t1_t0_mean_ms"], 3), f(r["t2_t1_mean_ms"], 3), f(r["t3_t2_mean_ms"], 3),
                  f(r["t4_t3_mean_ms"], 3)] for r in rows]
        _fill(self.table, ["Senaryo", "olay", "ok", "karşılandı", "geç", "kayıp/hata",
                           "R min", "R ort", "R maks", "min pay", "t1−t0 ort", "t2−t1 ort",
                           "t3−t2 ort", "t4−t3 ort"], table)
        miss = f" · eksik: {', '.join(res['missing'])}" if res["missing"] else ""
        self.status.setText(f"{len(res['files'])} grafik üretildi (ms, yalnız status=ok){miss}")
        self.show_image()

    def show_image(self):
        _, rel = self.IMAGES[self.img_cb.currentIndex()]
        path = HAFTA_ROOT / rel
        if not path.exists():
            self.img.setText(f"{rel} yok — analizi çalıştırın.")
            self._pix = None
            return
        self._pix = QPixmap(str(path))
        self._rescale()

    def _rescale(self):
        if self._pix and not self._pix.isNull():
            w = max(400, self.scroll.viewport().width() - 20)
            self.img.setPixmap(self._pix.scaledToWidth(w, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()
