"""PySide6 ana pencere: UART Monitor."""
from __future__ import annotations

import time
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from . import protocol as P
from .analysis_view import AnalysisView, MeasurementsView
from .link import SerialWorker, available_ports
from .metrics import DEADLINE_US, STAGES, summarize
from .session import MIN_PRESSES, WARMUP_S, Session, State

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "measurements"

SCENARIO_TEXT = {
    "S0": "Telemetri kapalı · ek iş yok (referans)",
    "S1": "Telemetri 10 Hz (100 ms) · ek iş yok",
    "S2": "Telemetri 50 Hz (20 ms) · ek iş yok",
    "S3": "Telemetri 100 Hz (10 ms) · ek iş yok",
    "S4": "Telemetri 100 Hz · ~2 ms CPU işi",
    "S5": "Telemetri 100 Hz · ~5 ms CPU işi",
}
TEL_HZ = {"S0": 0, "S1": 10, "S2": 50, "S3": 100, "S4": 100, "S5": 100}
STAGE_COLORS = ["#a78bfa", "#fbbf24", "#60a5fa", "#34d399"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART Monitor — hafta-01 buton yanıt süresi")
        self.resize(1200, 780)

        self.worker: SerialWorker | None = None
        self.session = Session()
        self.pending: list = []
        self.warmup_until: float | None = None
        self.info_deadline: float | None = None
        self.pc_stop = False   # STOP'u PC mi gönderdi? (kart butonuyla durdurulursa DUMP kartta)
        self.out_dir = DEFAULT_OUT

        self._build_ui()
        self._refresh_ports()

        self.ui_timer = QTimer(self, interval=100, timeout=self._flush)
        self.ui_timer.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)

        # Bağlantı
        top = QHBoxLayout()
        self.port_cb = QComboBox(minimumWidth=320)
        self.refresh_btn = QPushButton("↻", clicked=self._refresh_ports, maximumWidth=36)
        self.conn_btn = QPushButton("Bağlan", clicked=self._toggle_connect)
        self.conn_lbl = QLabel("● Bağlı değil")
        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color: gray")
        top.addWidget(QLabel("Port:"))
        top.addWidget(self.port_cb)
        top.addWidget(self.refresh_btn)
        top.addWidget(QLabel("115200 · 8N1"))
        top.addWidget(self.conn_btn)
        top.addWidget(self.conn_lbl)
        top.addStretch(1)
        top.addWidget(self.info_lbl)
        v.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        v.addWidget(split, 1)

        # Sol: deney kontrolü
        left = QWidget()
        lv = QVBoxLayout(left)
        g = QGroupBox("Deney")
        gl = QGridLayout(g)
        self.scn_cb = QComboBox()
        for k, t in SCENARIO_TEXT.items():
            self.scn_cb.addItem(f"{k} — {t}", k)
        self.scn_btn = QPushButton("1 · Senaryoyu ayarla (SCN)", clicked=self._cmd_scn)
        self.start_btn = QPushButton("2 · Başlat (START + 5 s ısınma)", clicked=self._cmd_start)
        self.stop_btn = QPushButton("3 · Durdur ve kayıtları al (STOP → DUMP)", clicked=self._cmd_stop)
        self.save_btn = QPushButton("4 · CSV kaydet", clicked=self._save)
        self.info_btn = QPushButton("INFO", clicked=lambda: self._send(P.CMD_INFO))
        self.autosave_cb = QCheckBox("DUMP bitince otomatik kaydet", checked=True)
        self.dir_btn = QPushButton("Klasör…", clicked=self._choose_dir)
        self.dir_lbl = QLabel(str(self.out_dir))
        self.dir_lbl.setWordWrap(True)
        self.dir_lbl.setStyleSheet("color: gray; font-size: 11px")
        for i, w in enumerate([self.scn_cb, self.scn_btn, self.start_btn, self.stop_btn,
                               self.save_btn, self.autosave_cb]):
            gl.addWidget(w, i, 0, 1, 2)
        gl.addWidget(self.dir_btn, 6, 0)
        gl.addWidget(self.info_btn, 6, 1)
        gl.addWidget(self.dir_lbl, 7, 0, 1, 2)
        lv.addWidget(g)

        hint = QLabel(
            "<b>Kontrol karttan: mavi USER butonu (PA0)</b><br>"
            "Boşta <b>kısa</b> bas: sonraki senaryo<br>"
            "Boşta <b>uzun</b> bas (≥ 1 s): başlat → 5 s ısınma<br>"
            "Ölçümde her basış bir olaydır; <b>30. basıştan sonra</b><br>"
            "deney kendiliğinden biter, kayıtlar gelir ve CSV kaydedilir.<br>"
            "<span style='color:gray'>(İsteğe bağlı PE7 butonu da aynı işi yapar.)</span>")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: #eef6ff; padding: 6px; border-radius: 4px")
        lv.addWidget(hint)

        s = QGroupBox("Durum")
        sl = QVBoxLayout(s)
        self.state_lbl = QLabel(State.IDLE.value, wordWrap=True)
        self.state_lbl.setFont(QFont("", 11, QFont.Bold))
        self.count_lbl = QLabel("Kabul edilen basış (BTN): 0 / 30")
        self.tel_lbl = QLabel("TEL: 0")
        self.err_lbl = QLabel("", wordWrap=True)
        self.err_lbl.setStyleSheet("color: #dc2626")
        for w in (self.state_lbl, self.count_lbl, self.tel_lbl, self.err_lbl):
            sl.addWidget(w)
        lv.addWidget(s)
        lv.addStretch(1)
        split.addWidget(left)

        # Sağ: canlı görünüm + sonuçlar
        right = QWidget()
        rv = QVBoxLayout(right)
        card = QFrame(frameShape=QFrame.StyledPanel)
        cl = QGridLayout(card)
        self.tel_title = QLabel("—")
        self.tel_title.setFont(QFont("", 12))
        self.tel_raw = QLabel("")
        self.tel_raw.setStyleSheet("color: gray; font-family: Consolas")
        self.btn_title = QLabel("—")
        self.btn_title.setFont(QFont("", 14, QFont.Bold))
        self.btn_title.setStyleSheet("color: #059669")
        self.btn_raw = QLabel("")
        self.btn_raw.setStyleSheet("color: gray; font-family: Consolas")
        cl.addWidget(QLabel("Telemetri"), 0, 0)
        cl.addWidget(self.tel_title, 1, 0)
        cl.addWidget(self.tel_raw, 2, 0)
        cl.addWidget(QLabel("Buton yanıtı"), 0, 1)
        cl.addWidget(self.btn_title, 1, 1)
        cl.addWidget(self.btn_raw, 2, 1)
        rv.addWidget(card)

        self.tabs = QTabWidget()
        rv.addWidget(self.tabs, 1)

        self.btn_list = QListWidget()
        self.tabs.addTab(self.btn_list, "BTN olayları")

        res = QWidget()
        resl = QVBoxLayout(res)
        pg.setConfigOptions(antialias=True)
        self.plot_r = pg.PlotWidget(title="R = t4 − t0 (ms) — olay numarasına göre")
        self.plot_r.setLabel("bottom", "event_id")
        self.plot_r.setLabel("left", "R", units="ms")
        self.plot_r.showGrid(x=True, y=True, alpha=0.3)
        self.plot_stage = pg.PlotWidget(title="Aşama ortalamaları (ms, yalnız ok)")
        self.stats_tbl = QTableWidget(0, 2)
        self.stats_tbl.setHorizontalHeaderLabels(["Metrik", "Değer"])
        self.stats_tbl.horizontalHeader().setStretchLastSection(True)
        h = QHBoxLayout()
        h.addWidget(self.plot_stage, 1)
        h.addWidget(self.stats_tbl, 1)
        resl.addWidget(self.plot_r, 3)
        resl.addLayout(h, 2)
        self.tabs.addTab(res, "Sonuçlar")

        self.raw_view = QPlainTextEdit(readOnly=True)
        self.raw_view.setMaximumBlockCount(3000)
        self.raw_view.setFont(QFont("Consolas", 9))
        self.tabs.addTab(self.raw_view, "Ham UART")

        # Kaydedilmiş gerçek ölçümler ve analiz (ham CSV'den)
        self.meas_view = MeasurementsView(lambda: self.out_dir)
        self.tabs.addTab(self.meas_view, "Ölçümler (kayıtlı)")
        self.analysis_view = AnalysisView(lambda: self.out_dir)
        self.tabs.addTab(self.analysis_view, "Analiz ve grafikler")
        self.meas_view.refresh()

        split.addWidget(right)
        split.setSizes([330, 870])
        self._update_buttons()

    # ------------------------------------------------------------- bağlantı
    def _refresh_ports(self):
        self.port_cb.clear()
        ports = available_ports()
        # USB-TTL'yi öne al; ST-LINK VCP bu kartta PA2/PA3'e bağlı değil
        ports.sort(key=lambda p: "STLink" in p[1])
        for dev, desc in ports:
            if "STLink" in desc:
                desc += "  ⚠ PA2/PA3'e bağlı değil"
            self.port_cb.addItem(desc, dev)

    def _toggle_connect(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            self.conn_lbl.setText("● Bağlı değil")
            self.conn_btn.setText("Bağlan")
            self.session.state = State.IDLE
        else:
            dev = self.port_cb.currentData()
            if not dev:
                QMessageBox.warning(self, "Port", "Seri port bulunamadı.")
                return
            self.worker = SerialWorker(dev)
            self.worker.lines.connect(self._on_lines)   # QObject slotu: ana iş parçacığında çalışır
            self.worker.failed.connect(self._on_fail)
            self.worker.start()
            self.conn_lbl.setText(f"● Bağlı: {dev}")
            self.conn_btn.setText("Bağlantıyı kes")
            self.session.info.clear()
            self.info_deadline = time.monotonic() + 2.5
            QTimer.singleShot(300, lambda: self._send(P.CMD_INFO))
        self._update_buttons()

    def _on_lines(self, items: list):
        self.pending.extend(items)

    def _on_fail(self, msg: str):
        QMessageBox.critical(self, "Seri port", msg)
        if self.worker:
            self.worker = None
        self.conn_lbl.setText("● Bağlı değil")
        self.conn_btn.setText("Bağlan")
        self._update_buttons()

    def _send(self, data: bytes):
        if self.worker:
            self.worker.send(data)
            self.raw_view.appendPlainText(f">> {data.decode().strip()}")

    # --------------------------------------------------------------- komutlar
    def _cmd_scn(self):
        self._send(P.cmd_scenario(self.scn_cb.currentData()))

    def _cmd_start(self):
        self._send(P.CMD_START)

    def _cmd_stop(self):
        if self.session.btn_seen < MIN_PRESSES and self.session.state is State.MEASURING:
            if QMessageBox.question(self, "Durdur",
                                    f"Yalnızca {self.session.btn_seen} basış var (hedef ≥ {MIN_PRESSES}). "
                                    "Yine de durdurulsun mu?") != QMessageBox.Yes:
                return
        self.pc_stop = True
        self._send(P.CMD_STOP)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Ölçüm klasörü", str(self.out_dir))
        if d:
            self.out_dir = Path(d)
            self.dir_lbl.setText(d)

    def _save(self):
        try:
            paths = self.session.save(self.out_dir)
        except FileExistsError as exc:
            if QMessageBox.question(self, "Üzerine yaz", f"{exc} zaten var. Üzerine yazılsın mı?") \
                    != QMessageBox.Yes:
                return
            paths = self.session.save(self.out_dir, overwrite=True)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Kaydet", str(exc))
            return
        self.statusBar().showMessage("Kaydedildi: " + ", ".join(p.name for p in paths), 8000)
        # Kaydedilen gerçek veriyle tabloyu ve analizi yenile
        self.meas_view.show_scenario(self.session.scenario)
        self.analysis_view.run()

    # ------------------------------------------------------------------ akış
    def _flush(self):
        """100 ms'de bir: biriken satırları işle, arayüzü güncelle."""
        batch, self.pending[:] = list(self.pending), []
        prev_state = self.session.state
        raw_lines = []
        for pc_t, line in batch:
            msg = self.session.feed_line(line, pc_t)
            if isinstance(msg, P.Btn):
                self.btn_list.insertItem(0, f"Butona basıldı · Olay {msg.event_id}    ({line.rstrip()})")
            if not isinstance(msg, P.Tel):
                raw_lines.append(line.rstrip())
        if raw_lines:
            self.raw_view.appendPlainText("\n".join(raw_lines))

        st = self.session
        if st.state is State.WARMUP and prev_state is not State.WARMUP:
            self.warmup_until = time.monotonic() + WARMUP_S + 0.2
            self.btn_list.clear()
        if st.state is State.WARMUP and self.warmup_until and time.monotonic() >= self.warmup_until:
            st.state = State.MEASURING
        if st.state is State.STOPPING and prev_state is not State.STOPPING:
            st.state = State.DUMPING
            if self.pc_stop:          # kart butonuyla durdurulduysa kart kendisi döker
                self._send(P.CMD_DUMP)
            self.pc_stop = False
        if st.state is State.DONE and prev_state is not State.DONE:
            self._show_results()
            if self.autosave_cb.isChecked():
                self._save()

        # Etiketler
        txt = st.state.value
        if st.state is State.WARMUP and self.warmup_until:
            txt += f"  ({max(0.0, self.warmup_until - time.monotonic()):.1f} s)"
        self.state_lbl.setText(f"{st.scenario or '—'} · {txt}")
        self.count_lbl.setText(f"Kabul edilen basış (BTN): {st.btn_seen} / {MIN_PRESSES}")
        self.tel_lbl.setText(f"TEL alındı: {st.tel_seen}")
        if st.last_tel:
            self.tel_title.setText(f"{st.last_tel.scenario} · Telemetri {TEL_HZ.get(st.last_tel.scenario, '?')} Hz")
            self.tel_raw.setText(f"TEL,{st.last_tel.seq},{st.last_tel.scenario},… work={st.last_tel.work_us} µs")
        if st.last_btn:
            self.btn_title.setText(f"Butona basıldı · Olay {st.last_btn.event_id}")
            self.btn_raw.setText(f"BTN,{st.last_btn.event_id},{st.last_btn.scenario},{st.last_btn.text}")
        if st.info:
            self.info_lbl.setText(f"FW {st.info.get('fw', '?')} · git {st.info.get('git', '?')} · "
                                  f"{int(st.info.get('sysclk_hz', 0)) // 1_000_000} MHz · "
                                  f"tick {st.info.get('tick_hz', '?')} Hz · build {st.info.get('build', '?')}")
        errs = st.errors[-3:]
        if self.worker and self.info_deadline and not st.info and time.monotonic() > self.info_deadline:
            errs = ["Karttan yanıt yok: doğru COM portu mu? (USB-TTL: PA2→RXD, PA3←TXD, GND)"] + errs
        self.err_lbl.setText("\n".join(errs))
        self._update_buttons()

    def _update_buttons(self):
        c = self.worker is not None
        s = self.session.state
        running = s in (State.WARMUP, State.MEASURING)
        self.scn_btn.setEnabled(c and not running)
        self.start_btn.setEnabled(c and s in (State.CONFIGURED, State.DONE))
        self.stop_btn.setEnabled(c and running)
        self.save_btn.setEnabled(s is State.DONE)
        self.info_btn.setEnabled(c and not running)

    # -------------------------------------------------------------- sonuçlar
    def _show_results(self):
        rows = sorted(self.session.rows, key=lambda r: r.event_id)
        self.plot_r.clear()
        ok = [(r.event_id, r.response_us / 1000) for r in rows if r.status == "ok" and r.response_us is not None]
        bad = [r.event_id for r in rows if r.status != "ok"]
        if ok:
            xs, ys = zip(*ok)
            self.plot_r.plot(xs, ys, pen=pg.mkPen("#60a5fa", width=1.5), symbol="o", symbolSize=6,
                             symbolBrush="#60a5fa", name="R (ok)")
        if bad:
            self.plot_r.plot(bad, [0] * len(bad), pen=None, symbol="x", symbolSize=10,
                             symbolBrush="#dc2626", symbolPen="#dc2626", name="kayıp/hata")
        self.plot_r.addItem(pg.InfiniteLine(pos=DEADLINE_US / 1000, angle=0,
                                            pen=pg.mkPen("#dc2626", style=Qt.DashLine),
                                            label="D = 20 ms", labelOpts={"position": 0.95}))

        s = summarize(rows)
        self.plot_stage.clear()
        bottom = 0.0
        for (label, *_), color in zip(STAGES, STAGE_COLORS):
            val = (s.get(f"{label.replace('-', '_')}_mean_us") or 0) / 1000
            self.plot_stage.addItem(pg.BarGraphItem(x=[0], height=[val], y0=[bottom], width=0.6,
                                                    brush=color, name=label))
            bottom += val
        self.plot_stage.getAxis("bottom").setTicks([[(0, self.session.scenario or "")]])

        def fmt(v):
            return "—" if v is None else (f"{v / 1000:.3f} ms" if isinstance(v, (int, float)) else str(v))

        items = [
            ("Toplam olay", s["n_events"]), ("Başarılı (ok)", s["n_ok"]),
            ("Deadline karşılandı", s["n_met"]), ("20 ms'yi aşan (tamamlanmış)", s["n_late"]),
            ("btn_drop", s["n_btn_drop"]), ("tx_drop", s["n_tx_drop"]),
            ("tx_error", s["n_tx_error"]), ("timeout", s["n_timeout"]),
            ("log_overflow (MCU)", self.session.counters.get("log_overflow", "—")),
            ("R min", fmt(s["R_min_us"])), ("R ortalama", fmt(s["R_mean_us"])),
            ("R p95", fmt(s["R_p95_us"])), ("R gözlenen maks.", fmt(s["R_max_us"])),
        ] + [(f"ort. {label}", fmt(s[f"{label.replace('-', '_')}_mean_us"])) for label, *_ in STAGES]
        self.stats_tbl.setRowCount(len(items))
        for i, (k, val) in enumerate(items):
            self.stats_tbl.setItem(i, 0, QTableWidgetItem(k))
            self.stats_tbl.setItem(i, 1, QTableWidgetItem(str(val)))
        self.tabs.setCurrentIndex(1)

    def closeEvent(self, e):
        if self.worker:
            self.worker.stop()
        super().closeEvent(e)


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
