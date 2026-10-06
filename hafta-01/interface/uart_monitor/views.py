"""Arayüz bileşenleri: grafit tema, deney planı, gecikme zinciri, olay şeridi, grafikler.

Tüm grafikler yalnızca GERÇEK ölçüm satırlarından (EventRow) çizilir.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Optional

import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .metrics import DEADLINE_US, STAGES, EventRow, read_counters, read_csv, summarize

# ---------------------------------------------------------------- tema (grafit + kehribar)
C = {
    "bg": "#111315", "panel": "#1a1d21", "panel2": "#15181b", "border": "#2a2f36",
    "text": "#e6e6e6", "muted": "#8b949e", "accent": "#f5a524", "cyan": "#22d3ee",
    "green": "#4ade80", "amber": "#fbbf24", "red": "#f87171", "violet": "#c084fc",
    "sky": "#38bdf8", "teal": "#2dd4bf",
}
STAGE_COLORS = [C["violet"], C["amber"], C["sky"], C["teal"]]
STAGE_SHORT = ["ISR → görev", "hazırlama", "kuyruk", "hat + TC"]
STAGE_NAMES = ["t₁−t₀  ISR → ButtonTask", "t₂−t₁  yanıt hazırlama", "t₃−t₂  kuyrukta bekleme",
               "t₄−t₃  UART hattı + TC"]
VARIANT_COLORS = {"A": "#9ca3af", "B": C["sky"], "C": C["accent"]}
VARIANTS = {
    "A": ("Görev standardı", "Tek TX FIFO · öncelik Tel 3 > Btn 2 > Uart 1"),
    "B": ("Öncelikli yanıt kuyruğu", "BTN, kuyruktaki TEL'lerin önünde gönderilir"),
    "C": ("B + görev önceliği", "Btn > Uart > Tel · yanıt CPU işini beklemez, UART aç kalmaz"),
}
# (ad, açıklama, telemetri Hz, ek CPU ms)
SCENARIOS = [("S0", "Telemetri kapalı", 0, 0), ("S1", "Telemetri 10 Hz", 10, 0),
             ("S2", "Telemetri 50 Hz", 50, 0), ("S3", "Telemetri 100 Hz", 100, 0),
             ("S4", "100 Hz + 2 ms CPU işi", 100, 2), ("S5", "100 Hz + 5 ms CPU işi", 100, 5)]
LINE_MS = 64 * 10 / 115200 * 1000            # bir mesajın hat süresi

QSS = f"""
QWidget {{ background: {C['bg']}; color: {C['text']}; font-family: 'Segoe UI'; font-size: 10pt; }}
QScrollArea, QSplitter {{ border: 0; }}
QFrame#panel {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 6px; }}
QFrame#panel QLabel, QWidget#clear {{ background: transparent; }}
QLabel#sec {{ color: {C['accent']}; font-weight: 700; font-size: 9pt; letter-spacing: 2px; }}
QLabel#muted {{ color: {C['muted']}; }}
QLabel#brand {{ font-size: 14pt; font-weight: 700; }}
QLabel#brandsub {{ color: {C['muted']}; font-size: 9pt; }}
QLabel#chip {{ border-radius: 4px; padding: 3px 7px; font-family: Consolas; font-size: 9pt; }}
QLabel#statv {{ font-size: 15pt; font-weight: 600; }}
QLabel#note {{ color: {C['muted']}; border-left: 3px solid {C['accent']}; padding: 4px 10px; }}
QPushButton {{ background: #22262b; border: 1px solid #343a42; border-radius: 5px; padding: 7px 12px; }}
QPushButton:hover {{ border-color: {C['accent']}; }}
QPushButton:disabled {{ color: #4b5058; background: #191c1f; border-color: {C['border']}; }}
QPushButton#go {{ background: {C['accent']}; border: 0; color: #1a1205; font-weight: 700; }}
QPushButton#go:disabled {{ background: #4a3a17; color: #7d6a45; }}
QPushButton#halt {{ background: #3a1d1d; border: 1px solid #7f2d2d; color: #fecaca; }}
QPushButton#halt:disabled {{ background: #1d1616; color: #5b4646; border-color: #2c2222; }}
QPushButton#row {{ text-align: left; background: {C['panel2']}; padding: 6px 10px; }}
QPushButton#row:checked {{ background: #2b2416; border: 1px solid {C['accent']}; }}
QPushButton#vcard {{ text-align: left; background: {C['panel2']}; padding: 7px 10px; }}
QPushButton#vcard:checked {{ background: #2b2416; border: 1px solid {C['accent']}; }}
QComboBox, QSpinBox {{ background: {C['panel2']}; border: 1px solid #343a42; border-radius: 5px; padding: 5px 8px; }}
QComboBox QAbstractItemView {{ background: {C['panel2']}; selection-background-color: #4a3a17; }}
QProgressBar {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 4px; height: 10px;
               text-align: center; color: {C['muted']}; font-size: 8pt; }}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 3px; }}
QTabWidget::pane {{ border: 1px solid {C['border']}; background: {C['panel']}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ background: transparent; border: 0; border-bottom: 2px solid transparent;
               padding: 8px 14px; color: {C['muted']}; }}
QTabBar::tab:selected {{ color: {C['text']}; border-bottom: 2px solid {C['accent']}; }}
QTableWidget {{ background: {C['panel2']}; gridline-color: {C['border']}; border: 0;
               alternate-background-color: #181b1f; selection-background-color: #4a3a17; }}
QHeaderView::section {{ background: {C['panel']}; color: {C['muted']}; border: 0;
                       border-bottom: 1px solid {C['border']}; padding: 5px; font-weight: 600; }}
QPlainTextEdit {{ background: {C['panel2']}; border: 0; font-family: Consolas; font-size: 9pt; }}
QCheckBox, QRadioButton {{ background: transparent; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 7px; border: 1px solid #5b626b; background: {C['panel2']}; }}
QRadioButton::indicator:checked {{ background: {C['accent']}; border: 1px solid {C['accent']}; }}
QToolTip {{ background: #22262b; color: {C['text']}; border: 1px solid #343a42; }}
"""


def setup_pg():
    pg.setConfigOptions(antialias=True, background=C["panel2"], foreground=C["muted"])


def panel(title: str | None = None):
    f = QFrame()
    f.setObjectName("panel")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 12)
    v.setSpacing(8)
    if title:
        t = QLabel(title.upper())
        t.setObjectName("sec")
        v.addWidget(t)
    return f, v


class KeyValues(QWidget):
    """Kompakt 'etiket ......... değer' listesi."""

    def __init__(self, keys: list[str]):
        super().__init__()
        self.setObjectName("clear")
        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(4)
        self.vals: dict[str, QLabel] = {}
        for i, k in enumerate(keys):
            kl = QLabel(k)
            kl.setObjectName("muted")
            vl = QLabel("—")
            vl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            vl.setFont(QFont("Consolas", 10))
            g.addWidget(kl, i, 0)
            g.addWidget(vl, i, 1)
            self.vals[k] = vl

    def set(self, key: str, value, color: str | None = None):
        lbl = self.vals[key]
        lbl.setText("—" if value is None or value == "" else str(value))
        lbl.setStyleSheet(f"color: {color};" if color else "")


# ---------------------------------------------------------------- deney planı
class LoadBar(QWidget):
    """İnce yüzde çubuğu (hat / CPU doluluğu)."""

    def __init__(self, frac: float, color: str):
        super().__init__()
        self.frac, self.color = frac, color
        self.setFixedHeight(5)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["border"]))
        p.drawRoundedRect(self.rect(), 2, 2)
        if self.frac > 0:
            r = self.rect().adjusted(0, 0, -int(self.width() * (1 - min(self.frac, 1))), 0)
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(r, 2, 2)


class ScenarioList(QWidget):
    """Dikey senaryo seçici; her satırda telemetri hat doluluğu ve ek CPU payı."""
    selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("clear")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.group = QButtonGroup(self)
        self.btns: dict[str, QPushButton] = {}
        for name, desc, hz, cpu in SCENARIOS:
            line = hz * LINE_MS / 1000
            cpuf = hz * cpu / 1000
            b = QPushButton()
            b.setObjectName("row")
            b.setCheckable(True)
            b.setToolTip(f"{name}: hat doluluğu (yalnız TEL) %{line * 100:.0f}, ek CPU %{cpuf * 100:.0f}")
            lay = QGridLayout(b)
            lay.setContentsMargins(10, 5, 10, 6)
            lay.setHorizontalSpacing(8)
            lay.setVerticalSpacing(2)
            n = QLabel(name)
            n.setFont(QFont("Consolas", 11, QFont.Bold))
            d = QLabel(desc)
            pct = QLabel(f"hat %{line * 100:.0f} · CPU %{cpuf * 100:.0f}")
            pct.setObjectName("muted")
            lb = LoadBar(line, C["cyan"])
            cb = LoadBar(cpuf, C["red"])
            for w in (n, d, pct, lb, cb):
                w.setAttribute(Qt.WA_TransparentForMouseEvents)
                w.setStyleSheet("background: transparent;") if isinstance(w, QLabel) else None
            lay.addWidget(n, 0, 0, 3, 1)
            lay.addWidget(d, 0, 1)
            lay.addWidget(pct, 0, 2, Qt.AlignRight)
            lay.addWidget(lb, 1, 1, 1, 2)
            lay.addWidget(cb, 2, 1, 1, 2)
            b.setMinimumHeight(52)
            b.clicked.connect(lambda _=False, x=name: self.selected.emit(x))
            self.group.addButton(b)
            self.btns[name] = b
            v.addWidget(b)

    def set_active(self, name: str | None):
        for n, b in self.btns.items():
            b.blockSignals(True)
            b.setChecked(n == name)
            b.blockSignals(False)

    def current(self) -> Optional[str]:
        return next((n for n, b in self.btns.items() if b.isChecked()), None)


class VariantCards(QWidget):
    selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("clear")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.group = QButtonGroup(self)
        self.btns: dict[str, QPushButton] = {}
        for k, (title, desc) in VARIANTS.items():
            b = QPushButton(f"{k}   {title}\n      {desc}")
            b.setObjectName("vcard")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, x=k: self.selected.emit(x))
            self.group.addButton(b)
            self.btns[k] = b
            v.addWidget(b)

    def set_active(self, key: str):
        for k, b in self.btns.items():
            b.blockSignals(True)
            b.setChecked(k == key)
            b.blockSignals(False)

    def current(self) -> str:
        return next((k for k, b in self.btns.items() if b.isChecked()), "A")


# ---------------------------------------------------------------- gecikme zinciri
class LatencyChain(QWidget):
    """EXTI ISR → ButtonTask → TX kuyruğu → UART hattı → TC akışı ve aşama süreleri."""

    NODES = ["EXTI ISR", "ButtonTask", "TX kuyruğu", "UART hattı", "TC kesmesi"]

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(132)
        self.title = "Henüz olay yok"
        self.stages: list[Optional[int]] = [None] * 4
        self.R: Optional[int] = None

    def set_event(self, title: str, stages: list, R: Optional[int]):
        self.title, self.stages, self.R = title, stages, R
        self.update()

    @staticmethod
    def _fmt(us):
        if us is None:
            return "…"
        return f"{us} µs" if us < 1000 else f"{us / 1000:.2f} ms"

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        right = 190
        usable = w - right - 20
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(10, 16, self.title)

        # düğümler ve oklar
        n = len(self.NODES)
        nw, nh, y = 92, 26, 34
        gap = (usable - n * nw) / (n - 1)
        xs = [10 + i * (nw + gap) for i in range(n)]
        for i, (x, name) in enumerate(zip(xs, self.NODES)):
            p.setPen(QPen(QColor(C["border"]), 1))
            p.setBrush(QColor(C["panel2"]))
            p.drawRoundedRect(QRectF(x, y, nw, nh), 4, 4)
            p.setPen(QColor(C["text"]))
            p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            p.drawText(QRectF(x, y, nw, nh), Qt.AlignCenter, name)
            if i < n - 1:
                ax0, ax1, ay = x + nw + 4, xs[i + 1] - 4, y + nh / 2
                col = QColor(STAGE_COLORS[i])
                p.setPen(QPen(col, 2))
                p.drawLine(int(ax0), int(ay), int(ax1), int(ay))
                p.drawLine(int(ax1), int(ay), int(ax1 - 6), int(ay - 4))
                p.drawLine(int(ax1), int(ay), int(ax1 - 6), int(ay + 4))
                p.setFont(QFont("Consolas", 9, QFont.Bold))
                p.drawText(QRectF(ax0, y - 16, ax1 - ax0, 14), Qt.AlignCenter, self._fmt(self.stages[i]))
                p.setPen(QColor(C["muted"]))
                p.setFont(QFont("Segoe UI", 7))
                p.drawText(QRectF(ax0, y + nh, ax1 - ax0, 12), Qt.AlignCenter, STAGE_SHORT[i])

        # orantılı zaman çubuğu (0 .. max(25 ms, R))
        by, bh = y + nh + 22, 16
        total_ms = max(25.0, (self.R or 0) / 1000 * 1.05)
        scale = usable / total_ms
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["panel2"]))
        p.drawRoundedRect(QRectF(10, by, usable, bh), 3, 3)
        x = 10.0
        for k, d in enumerate(self.stages):
            if d is None:
                break
            ww = max(1.5, d / 1000 * scale)
            p.setBrush(QColor(STAGE_COLORS[k]))
            p.drawRect(QRectF(x, by, ww, bh))
            x += d / 1000 * scale
        dx = 10 + DEADLINE_US / 1000 * scale
        p.setPen(QPen(QColor(C["red"]), 1.5, Qt.DashLine))
        p.drawLine(int(dx), int(by - 4), int(dx), int(by + bh + 4))
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(int(dx) + 3, int(by + bh + 12), "D = 20 ms")
        p.drawText(10, int(by + bh + 12), "0")
        p.drawText(int(10 + usable) - 40, int(by + bh + 12), f"{total_ms:.0f} ms")

        # sağ: R ve pay
        rx = w - right
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(rx, 30, "R = t₄ − t₀")
        p.setFont(QFont("Consolas", 22, QFont.Bold))
        if self.R is None:
            p.setPen(QColor(C["muted"]))
            p.drawText(rx, 62, "…")
        else:
            ok = self.R <= DEADLINE_US
            p.setPen(QColor(C["green"] if ok else C["red"]))
            p.drawText(rx, 62, f"{self.R / 1000:.2f} ms")
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(rx, 84, f"pay {(DEADLINE_US - self.R) / 1000:+.2f} ms  {'✓' if ok else '✗ deadline'}")


class EventStrip(QWidget):
    """Son olaylar: renkli çipler (yeşil ok, kehribar geç, kırmızı kayıp, gri sürüyor)."""

    def __init__(self, n: int = 20):
        super().__init__()
        self.setObjectName("clear")
        self.n = n
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        lbl = QLabel("Son olaylar")
        lbl.setObjectName("muted")
        lbl.setMinimumWidth(80)
        h.addWidget(lbl)
        self.chips: list[QLabel] = []
        for _ in range(n):
            c = QLabel("")
            c.setObjectName("chip")
            c.hide()
            self.chips.append(c)
            h.addWidget(c)
        h.addStretch(1)

    def set_items(self, items: list[tuple[str, str, str]]):
        """items: (metin, renk, ipucu); en yenisi sonda."""
        items = items[-self.n:]
        for i, c in enumerate(self.chips):
            if i < len(items):
                text, color, tip = items[i]
                last = i == len(items) - 1
                c.setText(text)
                c.setToolTip(tip)
                c.setStyleSheet(f"background: {color}22; color: {color}; "
                                f"border: 1px solid {color if last else color + '55'};")
                c.show()
            else:
                c.hide()


# ---------------------------------------------------------------- grafikler
class RChart(pg.PlotWidget):
    """Olay numarası -> R. ok: camgöbeği, geç: kehribar, kayıp: kırmızı × (R yok)."""

    def __init__(self):
        super().__init__()
        self.setMenuEnabled(False)
        self.setLabel("left", "R (ms)")
        self.setLabel("bottom", "olay kimliği")
        self.showGrid(x=False, y=True, alpha=0.12)

    def set_rows(self, rows: list[EventRow]):
        self.clear()
        ok = [(r.event_id, r.response_us / 1000) for r in rows if r.status == "ok" and r.response_us is not None]
        good = [(x, y) for x, y in ok if y * 1000 <= DEADLINE_US]
        late = [(x, y) for x, y in ok if y * 1000 > DEADLINE_US]
        bad = [r.event_id for r in rows if r.status != "ok"]
        if ok:
            self.plot(*zip(*ok), pen=pg.mkPen(C["border"], width=1))
        if good:
            self.plot(*zip(*good), pen=None, symbol="s", symbolSize=6, symbolBrush=C["cyan"], symbolPen=None)
        if late:
            self.plot(*zip(*late), pen=None, symbol="s", symbolSize=6, symbolBrush=C["amber"], symbolPen=None)
        if bad:
            self.plot(bad, [0] * len(bad), pen=None, symbol="x", symbolSize=9,
                      symbolBrush=C["red"], symbolPen=pg.mkPen(C["red"], width=1.5))
        self.addItem(pg.InfiniteLine(pos=DEADLINE_US / 1000, angle=0,
                                     pen=pg.mkPen(C["red"], width=1, style=Qt.DashLine)))
        ymax = max([y for _, y in ok] + [25])
        self.setYRange(0, ymax * 1.08, padding=0)
        if rows:
            self.setXRange(0, max(r.event_id for r in rows) + 1, padding=0.02)


class CdfChart(pg.PlotWidget):
    """R'nin kümülatif dağılımı: 'olayların yüzde kaçı X ms içinde yanıtlandı?'"""

    def __init__(self):
        super().__init__()
        self.setMenuEnabled(False)
        self.setLabel("bottom", "R (ms)")
        self.setLabel("left", "olayların payı (%)")
        self.showGrid(x=True, y=True, alpha=0.12)

    def set_rows(self, rows: list[EventRow]):
        self.clear()
        n = len(rows)
        vals = sorted(r.response_us / 1000 for r in rows if r.status == "ok" and r.response_us is not None)
        if not n or not vals:
            return
        xs, ys = [0.0], [0.0]
        for i, v in enumerate(vals, start=1):
            xs += [v, v]
            ys += [ys[-1], i / n * 100]      # kayıplar paydada: %100'e ulaşamaz
        self.plot(xs, ys, pen=pg.mkPen(C["accent"], width=2))
        self.addItem(pg.InfiniteLine(pos=DEADLINE_US / 1000, angle=90,
                                     pen=pg.mkPen(C["red"], width=1, style=Qt.DashLine)))
        self.addItem(pg.InfiniteLine(pos=100, angle=0, pen=pg.mkPen(C["border"], width=1)))
        self.setXRange(0, max(25.0, vals[-1] * 1.05), padding=0)
        self.setYRange(0, 105, padding=0)


class StageBars(pg.PlotWidget):
    """Aşama ortalamaları (yalnız ok) — yatay çubuklar ve maksimum işareti."""

    def __init__(self):
        super().__init__()
        self.setMenuEnabled(False)
        self.setLabel("bottom", "süre (ms) — çubuk: ortalama, |: en kötü")
        ax = self.getAxis("left")
        ax.setTicks([[(3 - i, n) for i, n in enumerate(STAGE_NAMES)]])
        ax.setWidth(190)
        self.showGrid(x=True, alpha=0.12)

    def set_rows(self, rows: list[EventRow]):
        self.clear()
        ok = [r for r in rows if r.status == "ok"]
        if not ok:
            return
        xmax = 0.0
        for i, (_, a, b, _) in enumerate(STAGES):
            vals = [r.stage_us(a, b) for r in ok]
            m = sum(vals) / len(vals) / 1000
            mx = max(vals) / 1000
            xmax = max(xmax, mx)
            y = 3 - i
            self.addItem(pg.BarGraphItem(x0=[0], y=[y], height=0.5, width=[m], brush=STAGE_COLORS[i], pen=None))
            self.plot([mx], [y], pen=None, symbol="|", symbolSize=18,
                      symbolPen=pg.mkPen(STAGE_COLORS[i], width=2))
            t = pg.TextItem(f"ort {m:.3f} · maks {mx:.3f}", color=C["text"], anchor=(0, 0.5))
            t.setPos(mx, y)
            self.addItem(t)
        self.setXRange(0, max(xmax * 1.6, 0.1), padding=0)
        self.setYRange(-0.6, 3.6, padding=0)


class LiveQueue(pg.PlotWidget):
    """TEL'den canlı: TX kuyruğu doluluğu (son ~20 s, MCU zamanı)."""

    def __init__(self):
        super().__init__()
        self.setMenuEnabled(False)
        self.setLabel("left", "TX kuyruğu (mesaj)")
        self.setLabel("bottom", "MCU zamanı (s)")
        self.showGrid(x=True, y=True, alpha=0.12)
        self.q: deque = deque(maxlen=2500)
        self.curve = self.plot(pen=pg.mkPen(C["cyan"], width=1.5))
        self.setYRange(0, 17, padding=0)
        self.addItem(pg.InfiniteLine(pos=16, angle=0, pen=pg.mkPen(C["red"], width=1, style=Qt.DashLine),
                                     label="kapasite 16", labelOpts={"position": 0.05, "color": C["red"]}))

    def push(self, t_us: int, depth: int):
        self.q.append((t_us / 1e6, depth))

    def clear_data(self):
        self.q.clear()
        self.curve.setData([], [])

    def refresh(self):
        if self.q:
            xs, ys = zip(*self.q)
            self.curve.setData(xs, ys)
            self.setXRange(max(xs[0], xs[-1] - 20), xs[-1] + 0.2, padding=0)


class EventTable(QTableWidget):
    COLS = ["olay", "durum", "t₀ (µs)", "t₁−t₀", "t₂−t₁", "t₃−t₂", "t₄−t₃", "R (ms)", "pay (ms)"]
    eventClicked = Signal(int)

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cellClicked.connect(lambda r, _c: self.eventClicked.emit(int(self.item(r, 0).text())))

    def set_rows(self, rows: list[EventRow], live: list | None = None):
        data = []
        if rows:
            for r in sorted(rows, key=lambda x: -x.event_id):
                data.append((r.event_id, r.status, r.t[0], [r.stage_us(k, k + 1) for k in range(4)],
                             r.response_us))
        elif live:
            for b in reversed(live):
                d1 = None if b.t0 is None or b.t1 is None else (b.t1 - b.t0) % (1 << 32)
                data.append((b.event_id, "sürüyor", b.t0, [d1, None, None, None], None))
        self.setRowCount(len(data))
        for i, (eid, status, t0, st, R) in enumerate(data):
            vals = [eid, status, "" if t0 is None else t0] + \
                   ["" if v is None else (f"{v} µs" if v < 1000 else f"{v / 1000:.3f} ms") for v in st] + \
                   ["" if R is None else f"{R / 1000:.3f}", "" if R is None else f"{(DEADLINE_US - R) / 1000:+.3f}"]
            color = (C["amber"] if status == "ok" and R and R > DEADLINE_US else
                     C["muted"] if status == "sürüyor" else C["red"] if status != "ok" else None)
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                if color and j in (1, 7, 8):
                    it.setForeground(QColor(color))
                self.setItem(i, j, it)


# ---------------------------------------------------------------- oturum dosyaları
def list_sessions(base: Path) -> list[tuple[str, Path, str]]:
    """(etiket, klasör, senaryo). Resmî set: base/Sx.csv. Diğerleri: base/runs/<V>-<SRC>/Sx.csv."""
    out = []
    for sc, *_ in SCENARIOS:
        if (base / f"{sc}.csv").exists():
            out.append((f"Resmî görev seti · A / HW · {sc}", base, sc))
    runs = base / "runs"
    if runs.exists():
        for d in sorted(p for p in runs.iterdir() if p.is_dir()):
            for sc, *_ in SCENARIOS:
                if (d / f"{sc}.csv").exists():
                    v, _, src = d.name.partition("-")
                    out.append((f"{v} / {src} · {sc}", d, sc))
    return out


def load_session(folder: Path, sc: str):
    return read_csv(folder / f"{sc}.csv"), read_counters(folder / f"{sc}_counters.csv")


def variant_dir(base: Path, variant: str, source: str) -> Optional[Path]:
    d = base / "runs" / f"{variant}-{source}"
    if d.exists():
        return d
    if variant == "A" and source == "HW":
        return base          # resmî set
    return None


def _heat(value_ms: Optional[float], lost: int) -> QColor:
    """Isı rengi: deadline'a yakınlık (yeşil → kehribar → kırmızı)."""
    if value_ms is None:
        return QColor(C["panel2"])
    if lost or value_ms > DEADLINE_US / 1000:
        return QColor("#5c1f1f")
    f = value_ms / (DEADLINE_US / 1000)
    if f < 0.6:
        return QColor("#173a2a")
    if f < 0.8:
        return QColor("#3d3414")
    return QColor("#4a2a12")


class VariantMatrix(QWidget):
    """Varyant × senaryo ısı tablosu + en kötü R eğrileri + ayrıntı tablosu."""

    METRICS = [("En kötü R (ms)", "R_max_us"), ("Ortalama R (ms)", "R_mean_us"),
               ("p95 R (ms)", "R_p95_us"), ("Kayıp + geç", None)]

    def __init__(self, base_getter):
        super().__init__()
        self._base = base_getter
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Kaynak"))
        self.src = QComboBox()
        self.src.addItem("Otomatik tetik (INJ)", "INJ")
        self.src.addItem("Fiziksel buton (HW)", "HW")
        self.src.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.src)
        top.addWidget(QLabel("   Hücre"))
        self.metric = QComboBox()
        for name, key in self.METRICS:
            self.metric.addItem(name, key)
        self.metric.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.metric)
        top.addStretch(1)
        self.note = QLabel("")
        self.note.setObjectName("muted")
        top.addWidget(self.note)
        v.addLayout(top)

        mid = QHBoxLayout()
        self.grid = QTableWidget(3, 6)
        short = {"S0": "kapalı", "S1": "10 Hz", "S2": "50 Hz", "S3": "100 Hz", "S4": "+2 ms CPU", "S5": "+5 ms CPU"}
        self.grid.setHorizontalHeaderLabels([f"{s}\n{short[s]}" for s, *_ in SCENARIOS])
        self.grid.setVerticalHeaderLabels([f"{k} · {VARIANTS[k][0]}" for k in "ABC"])
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.setMinimumHeight(200)
        mid.addWidget(self.grid, 3)
        self.curve = pg.PlotWidget()
        self.curve.setMenuEnabled(False)
        self.curve.setLabel("left", "en kötü R (ms)")
        self.curve.getAxis("bottom").setTicks([[(i, s) for i, (s, *_r) in enumerate(SCENARIOS)]])
        self.curve.showGrid(y=True, alpha=0.12)
        self.legend = self.curve.addLegend(offset=(-10, 5))
        mid.addWidget(self.curve, 2)
        v.addLayout(mid, 2)

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        v.addWidget(self.table, 2)

    def refresh(self):
        base = Path(self._base())
        src = self.src.currentData()
        key = self.metric.currentData()
        self.curve.clear()
        self.legend.clear()
        rows_out, found = [], []
        for vi, var in enumerate("ABC"):
            d = variant_dir(base, var, src)
            xs, ys = [], []
            for si, (sc, *_r) in enumerate(SCENARIOS):
                cell = QTableWidgetItem("—")
                cell.setTextAlignment(Qt.AlignCenter)
                p = None if d is None else d / f"{sc}.csv"
                if p is not None and p.exists():
                    rows = read_csv(p)
                    cnt = read_counters(d / f"{sc}_counters.csv")
                    s = summarize(rows)
                    lost = s["n_btn_drop"] + s["n_tx_drop"] + s["n_tx_error"] + s["n_timeout"]
                    worst = None if s["R_max_us"] is None else s["R_max_us"] / 1000
                    if key:
                        val = s[key]
                        txt = "—" if val is None else f"{val / 1000:.2f}"
                    else:
                        txt = f"{lost} + {s['n_late']}"
                    tel_drop = cnt.get("CNT.tel_tx_drop", "0") or "0"
                    if lost or s["n_late"] or tel_drop != "0":
                        txt += f"\n{s['n_late']} geç · {lost} kayıp · {tel_drop} TEL"
                    cell.setText(txt)
                    cell.setBackground(_heat(worst, lost))
                    cell.setToolTip(f"{var}/{src} {sc}: {s['n_ok']}/{s['n_events']} ok, en kötü {worst} ms")
                    if worst is not None:
                        xs.append(si)
                        ys.append(min(worst, 40.0))
                    rows_out.append([var, sc, f"{s['n_ok']}/{s['n_events']}",
                                     f"{(s['R_mean_us'] or 0) / 1000:.2f}",
                                     "" if s["R_p95_us"] is None else f"{s['R_p95_us'] / 1000:.2f}",
                                     "" if worst is None else f"{worst:.2f}", s["n_late"], lost, tel_drop,
                                     "" if s["margin_min_us"] is None else f"{s['margin_min_us'] / 1000:+.2f}"])
                self.grid.setItem(vi, si, cell)
            if xs:
                found.append(var)
                c = VARIANT_COLORS[var]
                self.curve.plot(xs, ys, pen=pg.mkPen(c, width=2), symbol="o", symbolSize=7,
                                symbolBrush=c, symbolPen=None, name=f"{var}")
        self.curve.addItem(pg.InfiniteLine(pos=DEADLINE_US / 1000, angle=0,
                                           pen=pg.mkPen(C["red"], width=1, style=Qt.DashLine)))
        self.curve.setYRange(0, 42, padding=0)
        self.curve.setXRange(-0.3, 5.3, padding=0)

        hdr = ["Varyant", "Senaryo", "ok / olay", "R ort.", "R p95", "R en kötü", "20 ms aşımı",
               "kayıp", "TEL düşen", "min pay"]
        self.table.setColumnCount(len(hdr))
        self.table.setHorizontalHeaderLabels(hdr)
        self.table.setRowCount(len(rows_out))
        for i, row in enumerate(rows_out):
            for j, val in enumerate(row):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                if j == 0:
                    it.setForeground(QColor(VARIANT_COLORS[row[0]]))
                if j in (6, 7, 8) and str(val) not in ("0", ""):
                    it.setForeground(QColor(C["red"]))
                self.table.setItem(i, j, it)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        missing = [v for v in "ABC" if v not in found]
        self.note.setText(("Ölçülmemiş varyant: " + ", ".join(missing)) if missing else
                          "Renk: yeşil < 12 ms · kehribar < 16 ms · turuncu < 20 ms · kırmızı: aşım/kayıp. "
                          "Eğri 40 ms'de kesilir.")
