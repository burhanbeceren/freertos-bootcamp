"""PySide6 ana pencere: Yanıt Süresi Laboratuvarı (hafta-01).

Kart -> PC: UART (FTDI RX). PC -> kart: UART TX ya da ST-LINK posta kutusu (otomatik).
Arayüz ölçümü gösterir, ölçüme karışmaz: bütün zaman damgaları MCU'dan (TIM2) gelir.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QScrollArea,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from . import protocol as P
from .analysis_view import AnalysisView
from .control import CommandChannel
from .link import SerialWorker, available_ports
from .metrics import DEADLINE_US, summarize
from .session import WARMUP_S, Session, State
from .views import (C, QSS, CdfChart, EventStrip, EventTable, KeyValues, LatencyChain, LiveQueue, RChart,
                    ScenarioList, StageBars, VariantCards, VariantMatrix, list_sessions, load_session,
                    panel, setup_pg)

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "measurements"
LIVE = "● Canlı oturum (karttan)"

GUIDE = """<h3>Akış</h3>
<ol>
<li><b>Bağlan</b>: USB-TTL portu (ST-LINK'in COM portu bu kartta PA2/PA3'e bağlı değildir).
Komutlar UART TX çalışmıyorsa ST-LINK posta kutusu ile gider; sol üstte görünür.</li>
<li><b>Deney planı</b>: senaryo (hat ve CPU doluluğu satırda), varyant, uyarım kaynağı, olay sayısı.</li>
<li><b>Başlat</b>: 5 s ısınma, sonra ölçüm. Olay sayısına ulaşınca kart son yanıtın hattan çıkmasını
telemetri açıkken bekler, sonra kendisi durur ve kayıtları gönderir. Oturum
<code>measurements/runs/&lt;V&gt;-&lt;KAYNAK&gt;/</code> altına kaydedilir.</li>
</ol>
<h3>Varyantlar</h3>
<ul>
<li><b>A</b> görev standardı · tek TX FIFO · Telemetry 3 &gt; Button 2 &gt; UartTx 1</li>
<li><b>B</b> öncelikli yanıt kuyruğu · BTN, kuyruktaki TEL'lerin arkasında beklemez (t₃−t₂)</li>
<li><b>C</b> B + Button &gt; UartTx &gt; Telemetry · CPU işini beklemez (t₁−t₀), UART aç kalmaz</li>
</ul>
<h3>Uyarım</h3>
<ul>
<li><b>Fiziksel buton</b>: kartın mavi USER butonu.</li>
<li><b>Otomatik tetik</b>: TIM7, EXTI0'ı yazılımla 0,5–0,9 s rastgele aralıkla tetikler. ISR'dan sonrası fiziksel basışla aynıdır.</li>
<li><b>Kesme gecikmesi ölç</b>: yazılım tetiğinden ISR'daki ilk ölçüme kadar geçen süre (DWT, 100 örnek).</li>
</ul>
<p>Yalnız <code>ok</code> olaylar R istatistiğine girer; kayıplar ayrı sayılır. Gözlenen en kötü değer kanıtlanmış worst-case değildir.</p>
"""


class CmdBus(QObject):
    status = Signal(str)


class CommandWorker(threading.Thread):
    """Komutları sırayla gönderir; her biri için kartın ACK/NAK yanıtını bekler (posta kutusu tek kayıtlık)."""

    def __init__(self, chan: CommandChannel, bus: CmdBus):
        super().__init__(daemon=True)
        self.chan, self.bus = chan, bus
        self.q: queue.Queue = queue.Queue()
        self.replies: list = []
        self.lock = threading.Lock()

    def push_reply(self, r: P.Reply):
        with self.lock:
            self.replies.append(r)
            del self.replies[:-50]

    def submit(self, cmd: str, key: str, timeout: float = 4.0):
        self.q.put((cmd, key, timeout))

    def run(self):
        while True:
            cmd, key, timeout = self.q.get()
            if cmd is None:
                return
            with self.lock:
                self.replies.clear()
            ok, err = self.chan.send(cmd)
            if not ok:
                self.bus.status.emit(f"Komut gönderilemedi ({cmd}): {err}")
                continue
            t_end = time.monotonic() + timeout
            done = False
            while time.monotonic() < t_end and not done:
                with self.lock:
                    done = any((r.tag in ("ACK", "NAK") and r.args[:1] == [key]) or
                               (key == "EXT" and r.tag == "EXT") for r in self.replies)
                time.sleep(0.02)
            if not done:
                self.bus.status.emit(f"Karttan yanıt gelmedi: {cmd}")


def stat_cell(title: str):
    w = QWidget()
    w.setObjectName("clear")
    v = QVBoxLayout(w)
    v.setContentsMargins(10, 2, 10, 2)
    v.setSpacing(0)
    t = QLabel(title)
    t.setObjectName("muted")
    val = QLabel("—")
    val.setObjectName("statv")
    v.addWidget(t)
    v.addWidget(val)
    return w, val


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        setup_pg()
        self.setWindowTitle("Yanıt Süresi Laboratuvarı — hafta-01")
        self.resize(1600, 1000)
        self.setStyleSheet(QSS)

        self.worker: SerialWorker | None = None
        self.session = Session()
        self.pending: list = []
        self.out_dir = DEFAULT_OUT
        self.warmup_until: float | None = None
        self.selected_event: int | None = None
        self.view_rows: list = []
        self.view_counters: dict = {}
        self.view_label = LIVE
        self.info_deadline: float | None = None
        self._last_key = None

        self.bus = CmdBus()
        self.bus.status.connect(self._note)
        self.chan = CommandChannel(write_uart=self._uart_write)
        self.cmds = CommandWorker(self.chan, self.bus)
        self.cmds.start()

        self._build_ui()
        self._refresh_ports()
        self._refresh_sessions()
        self.ui_timer = QTimer(self, interval=100, timeout=self._flush)
        self.ui_timer.start()

    # ================================================================== UI
    def _build_ui(self):
        split = QSplitter(Qt.Horizontal)
        self.setCentralWidget(split)

        # ---------------- sol kenar çubuğu
        side = QWidget()
        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 12, 8, 12)
        sv.setSpacing(10)
        brand = QLabel("Yanıt Süresi Laboratuvarı")
        brand.setObjectName("brand")
        sub = QLabel("STM32F407 · FreeRTOS · buton → UART yanıtı")
        sub.setObjectName("brandsub")
        sv.addWidget(brand)
        sv.addWidget(sub)

        f, l = panel("Bağlantı")
        self.port_cb = QComboBox()
        l.addWidget(self.port_cb)
        row = QHBoxLayout()
        self.conn_btn = QPushButton("Bağlan", clicked=self._connect)
        self.disc_btn = QPushButton("Kes", clicked=self._disconnect)
        row.addWidget(self.conn_btn, 2)
        row.addWidget(self.disc_btn, 1)
        row.addWidget(QPushButton("↻", clicked=self._refresh_ports, toolTip="Portları yenile"))
        l.addLayout(row)
        self.link_kv = KeyValues(["Durum", "Komut kanalı", "Firmware"])
        self.link_kv.set("Durum", "bağlı değil", C["red"])
        l.addWidget(self.link_kv)
        sv.addWidget(f)

        f, l = panel("Deney planı")
        self.scn_list = ScenarioList()
        self.scn_list.selected.connect(self._on_scenario)
        l.addWidget(self.scn_list)
        self.var_cards = VariantCards()
        self.var_cards.selected.connect(self._on_variant)
        self.var_cards.set_active("A")
        l.addWidget(self.var_cards)
        g = QGridLayout()
        g.addWidget(QLabel("Uyarım"), 0, 0)
        self.src_hw = QRadioButton("Fiziksel buton", checked=True)
        self.src_inj = QRadioButton("Otomatik tetik (EXTI)")
        self.src_hw.toggled.connect(self._on_source)
        g.addWidget(self.src_hw, 0, 1)
        g.addWidget(self.src_inj, 0, 2)
        g.addWidget(QLabel("Olay sayısı"), 1, 0)
        self.n_spin = QSpinBox()
        self.n_spin.setRange(5, 128)
        self.n_spin.setValue(30)
        g.addWidget(self.n_spin, 1, 1)
        self.autosave_cb = QCheckBox("Bitince kaydet", checked=True)
        g.addWidget(self.autosave_cb, 1, 2)
        l.addLayout(g)
        row = QHBoxLayout()
        self.start_btn = QPushButton("Başlat", clicked=self._start)
        self.start_btn.setObjectName("go")
        self.stop_btn = QPushButton("Durdur + kayıtları al", clicked=self._stop)
        self.stop_btn.setObjectName("halt")
        row.addWidget(self.start_btn, 1)
        row.addWidget(self.stop_btn, 1)
        l.addLayout(row)
        self.exti_btn = QPushButton("Kesme gecikmesini ölç (EXTI, 100×)", clicked=self._exti_test)
        l.addWidget(self.exti_btn)
        sv.addWidget(f)

        f, l = panel("Kart")
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m olay")
        self.progress.setMaximum(30)
        l.addWidget(self.progress)
        self.card_kv = KeyValues(["Durum", "Senaryo / varyant", "Sıcaklık", "VDDA", "TEL periyodu",
                                  "Ek CPU işi", "TEL / sıra boşluğu", "Hatalı satır", "Kesme gecikmesi"])
        l.addWidget(self.card_kv)
        sv.addWidget(f)
        sv.addStretch(1)
        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setWidget(side)
        side_scroll.setMinimumWidth(500)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        split.addWidget(side_scroll)

        # ---------------- sağ ana alan
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(8, 12, 14, 12)
        mv.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(QLabel("Görüntülenen oturum"))
        self.sess_cb = QComboBox()
        self.sess_cb.setMinimumWidth(320)
        self.sess_cb.currentIndexChanged.connect(self._on_session_selected)
        top.addWidget(self.sess_cb)
        top.addWidget(QPushButton("Klasör…", clicked=self._choose_dir))
        self.save_btn = QPushButton("Kaydet", clicked=self._save)
        top.addWidget(self.save_btn)
        top.addStretch(1)
        self.note = QLabel("Bağlanın ve deney planını seçin.")
        self.note.setObjectName("note")
        top.addWidget(self.note, 3)
        mv.addLayout(top)

        f, l = panel("Gecikme zinciri")
        self.chain = LatencyChain()
        l.addWidget(self.chain)
        self.strip = EventStrip()
        l.addWidget(self.strip)
        mv.addWidget(f)

        f, l = panel(None)
        sr = QHBoxLayout()
        sr.setSpacing(0)
        self.stats = {}
        for key, title in [("n", "ok / olay"), ("med", "medyan R"), ("p95", "p95 R"), ("max", "en kötü R"),
                           ("met", "deadline başarısı"), ("lost", "kayıp · log taşma"), ("margin", "en küçük pay")]:
            w, val = stat_cell(title)
            self.stats[key] = val
            sr.addWidget(w, 1)
        l.addLayout(sr)
        mv.addWidget(f)

        self.tabs = QTabWidget()
        t1 = QWidget()
        h = QHBoxLayout(t1)
        self.rchart = RChart()
        self.cdf = CdfChart()
        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self.rchart)
        sp.addWidget(self.cdf)
        sp.setSizes([700, 420])
        h.addWidget(sp)
        self.tabs.addTab(t1, "Yanıt süreleri")
        self.stagebars = StageBars()
        self.tabs.addTab(self.stagebars, "Aşamalar")
        self.events = EventTable()
        self.events.eventClicked.connect(self._on_event_clicked)
        self.tabs.addTab(self.events, "Olay tablosu")
        self.matrix = VariantMatrix(lambda: self.out_dir)
        self.tabs.addTab(self.matrix, "Varyant matrisi")
        self.liveq = LiveQueue()
        self.tabs.addTab(self.liveq, "Canlı kuyruk")
        self.analysis_view = AnalysisView(lambda: self.out_dir)
        self.tabs.addTab(self.analysis_view, "Rapor grafikleri")
        tw = QWidget()
        th = QHBoxLayout(tw)
        self.raw_view = QPlainTextEdit(readOnly=True)
        self.raw_view.setMaximumBlockCount(3000)
        th.addWidget(self.raw_view, 3)
        self.cnt_tbl = QTableWidget(0, 2)
        self.cnt_tbl.setHorizontalHeaderLabels(["Sayaç", "Değer"])
        self.cnt_tbl.verticalHeader().setVisible(False)
        self.cnt_tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cnt_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        th.addWidget(self.cnt_tbl, 2)
        guide = QLabel(GUIDE)
        guide.setWordWrap(True)
        guide.setTextFormat(Qt.RichText)
        guide.setAlignment(Qt.AlignTop)
        gs = QScrollArea()
        gs.setWidgetResizable(True)
        gs.setWidget(guide)
        th.addWidget(gs, 3)
        self.tabs.addTab(tw, "Ham akış · sayaçlar · yardım")
        mv.addWidget(self.tabs, 1)
        split.addWidget(main)
        split.setSizes([500, 1100])
        self._update_buttons()

    # ============================================================ bağlantı
    def _refresh_ports(self):
        self.port_cb.clear()
        ports = available_ports()
        ports.sort(key=lambda p: "STLink" in p[1])          # USB-TTL önce
        for dev, desc in ports:
            if "STLink" in desc:
                desc += "  ⚠ PA2/PA3'e bağlı değil"
            self.port_cb.addItem(desc, dev)

    def _uart_write(self, data: bytes):
        if self.worker:
            self.worker.send(data)

    def _connect(self):
        dev = self.port_cb.currentData()
        if not dev or self.worker:
            return
        self.worker = SerialWorker(dev)
        self.worker.lines.connect(self._on_lines)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()
        self.link_kv.set("Durum", f"bağlı · {dev}", C["green"])
        self.session = Session()
        self.liveq.clear_data()
        self.info_deadline = time.monotonic() + 3.0
        self.chan.mode = "uart"
        self.link_kv.set("Komut kanalı", "deneniyor…")
        QTimer.singleShot(250, lambda: self._send("PING", "PING", 1.0))
        QTimer.singleShot(1500, self._choose_channel)
        self._update_buttons()

    def _choose_channel(self):
        got = any(r.tag == "ACK" and r.args[:1] == ["PING"] for r in self.session.replies)
        if not got:
            self.chan.mode = "swd" if self.chan.swd.available else "uart"
        if self.chan.mode == "swd" or got:
            self.link_kv.set("Komut kanalı", self.chan.describe(), C["accent"])
            self._send("INFO", "INFO", 6.0)
            self._note(f"Bağlandı. Komutlar: {self.chan.describe()}.")
        else:
            self.link_kv.set("Komut kanalı", "yok — yalnız izleme", C["red"])
            self._note("PC → kart kanalı yok: kontrol kartın mavi butonundan.")

    def _disconnect(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.link_kv.set("Durum", "bağlı değil", C["red"])
        self.session.state = State.IDLE
        self._update_buttons()

    def _on_lines(self, items: list):
        self.pending.extend(items)

    def _on_fail(self, msg: str):
        QMessageBox.critical(self, "Seri port", msg)
        self._disconnect()

    def _send(self, cmd: str, key: str, timeout: float = 4.0):
        if not self.worker:
            return
        self.raw_view.appendPlainText(f">> {cmd}   [{self.chan.describe()}]")
        self.cmds.submit(cmd, key, timeout)

    def _note(self, text: str):
        self.note.setText(text)

    # ============================================================ komutlar
    def _running(self):
        return self.session.state in (State.WARMUP, State.MEASURING, State.STOPPING, State.DUMPING)

    def _on_scenario(self, name: str):
        if self._running():
            self.scn_list.set_active(self.session.scenario)
            return
        self._send(f"SCN,{name}", "SCN")

    def _on_variant(self, v: str):
        if self.worker and not self._running():
            self._send(f"VAR,{v}", "VAR")

    def _source(self) -> str:
        return "INJ" if self.src_inj.isChecked() else "HW"

    def _on_source(self):
        if self.worker and not self._running():
            self._send(f"SRC,{self._source()}", "SRC")

    def _start(self):
        scn = self.scn_list.current() or self.session.scenario or "S0"
        self._send(f"VAR,{self.var_cards.current()}", "VAR")
        self._send(f"SRC,{self._source()}", "SRC")
        self._send(f"EVN,{self.n_spin.value()}", "EVN")
        self._send(f"SCN,{scn}", "SCN")
        self._send("START", "START")
        self.liveq.clear_data()
        self.sess_cb.setCurrentIndex(0)

    def _stop(self):
        self._send("STOP", "STOP", 15.0)
        self._send("DUMP", "DUMP", 15.0)

    def _exti_test(self):
        self._send("EXTI", "EXT", 5.0)

    # ============================================================ akış
    def _flush(self):
        batch, self.pending[:] = list(self.pending), []
        st = self.session
        prev = st.state
        raw = []
        for pc_t, line in batch:
            msg = st.feed_line(line, pc_t)
            if isinstance(msg, P.Reply):
                self.cmds.push_reply(msg)
            if isinstance(msg, P.Tel):
                if msg.txq is not None:
                    self.liveq.push(msg.t_us, msg.txq)
            else:
                raw.append(line.rstrip())
        if raw:
            self.raw_view.appendPlainText("\n".join(raw))

        if st.state is State.WARMUP and prev is not State.WARMUP:
            self.warmup_until = time.monotonic() + WARMUP_S + 0.2
            self._note(f"{st.scenario} · {st.variant}/{st.source}: 5 s ısınma — butona basmayın.")
        if st.state is State.WARMUP and self.warmup_until and time.monotonic() >= self.warmup_until:
            st.state = State.MEASURING
            self._note(("Ölçüm: butona basın (aralar ≥ 0,5 s). " if st.source == "HW" else
                        "Ölçüm: otomatik tetik çalışıyor. ") +
                       f"{st.target_n} olaydan sonra kart kendisi durur; t₃/t₄ kayıtlar gelince görünür.")
        if st.state is State.STOPPING and prev is not State.STOPPING:
            st.state = State.DUMPING
        if st.state is State.DONE and prev is not State.DONE:
            self._note("Kayıtlar alındı.")
            if self.autosave_cb.isChecked():
                self._save()
        if st.ext_test and any(l.startswith("EXT,") for _, l in batch):
            n, mn, mean, mx, clk = st.ext_test
            ns = 1e9 / clk
            self._note(f"Kesme gecikmesi ({n} örnek): yazılım tetiği → ISR ilk ölçüm "
                       f"min {mn * ns:.0f} / ort {mean * ns:.0f} / maks {mx * ns:.0f} ns.")

        self._update_side()
        if self.tabs.currentWidget() is self.liveq:
            self.liveq.refresh()
        if self.view_label == LIVE:
            self._render_view(st.rows, st.counters, live=st.live_btn)
        self._update_buttons()

    def _update_side(self):
        st = self.session
        if st.scenario and not self._running():
            self.scn_list.set_active(st.scenario)      # kart butonuyla da değişebilir
        txt = st.state.value
        if st.state is State.WARMUP and self.warmup_until:
            txt += f" {max(0.0, self.warmup_until - time.monotonic()):.1f} s"
        ck = self.card_kv
        ck.set("Durum", txt, C["accent"] if self._running() else None)
        ck.set("Senaryo / varyant", f"{st.scenario or '—'} · {st.variant} · {st.source}")
        self.progress.setMaximum(max(1, st.target_n))
        self.progress.setValue(min(st.btn_seen, st.target_n))
        tl = st.last_tel
        if tl:
            ck.set("Sıcaklık", None if tl.temp_dC is None else f"{tl.temp_dC / 10:.1f} °C", C["cyan"])
            ck.set("VDDA", None if tl.vdda_mV is None else f"{tl.vdda_mV} mV")
            per = st.tel_period_us()
            ck.set("TEL periyodu", None if per is None else f"{per / 1000:.2f} ms")
            ck.set("Ek CPU işi", f"{tl.work_us} µs")
        ck.set("TEL / sıra boşluğu", f"{st.tel_seen} / {st.tel_gaps}", C["red"] if st.tel_gaps else None)
        ck.set("Hatalı satır", len(st.errors), C["red"] if st.errors else None)
        if st.ext_test:
            n, mn, mean, mx, clk = st.ext_test
            ck.set("Kesme gecikmesi", f"{mean * 1e9 / clk:.0f} ns ({mn}–{mx} çvr)")
        if st.info:
            self.link_kv.set("Firmware", f"{st.info.get('fw', '?')} · {st.info.get('git', '?')}")
            self.info_deadline = None
        elif self.worker and self.info_deadline and time.monotonic() > self.info_deadline:
            self.link_kv.set("Firmware", "yanıt yok — RESET", C["red"])

    def _update_buttons(self):
        c = self.worker is not None
        run = self._running()
        self.start_btn.setEnabled(c and not run)
        self.stop_btn.setEnabled(c and run)
        self.exti_btn.setEnabled(c and not run)
        for b in list(self.scn_list.btns.values()) + list(self.var_cards.btns.values()):
            b.setEnabled(not run)
        for w in (self.src_hw, self.src_inj, self.n_spin):
            w.setEnabled(not run)
        self.conn_btn.setEnabled(not c)
        self.disc_btn.setEnabled(c)
        self.save_btn.setEnabled(self.session.state is State.DONE)

    # ============================================================ görüntü
    def _render_view(self, rows, counters, live=None):
        key = (id(rows), len(rows), len(live or []), self.selected_event)
        if self._last_key == key:
            return
        self._last_key = key
        self.view_rows, self.view_counters = rows, counters
        self.rchart.set_rows(rows)
        self.cdf.set_rows(rows)
        self.stagebars.set_rows(rows)
        self.events.set_rows(rows, live)

        # gecikme zinciri: seçili olay, yoksa son olay
        ev = None
        if self.selected_event is not None:
            ev = next((r for r in rows if r.event_id == self.selected_event), None)
        if ev is None and rows:
            okr = [r for r in rows if r.status == "ok"]          # tam zinciri olan son olay
            ev = max(okr or rows, key=lambda r: r.event_id)
        if ev is not None:
            st = [ev.stage_us(k, k + 1) for k in range(4)]
            self.chain.set_event(f"Olay #{ev.event_id} · {ev.scenario} · {ev.status}", st, ev.response_us)
        elif live:
            b = live[-1]
            d1 = None if b.t0 is None or b.t1 is None else (b.t1 - b.t0) % (1 << 32)
            self.chain.set_event(f"Olay #{b.event_id} · ölçüm sürüyor (t₃/t₄ kartta)", [d1, None, None, None], None)
        else:
            self.chain.set_event("Henüz olay yok", [None] * 4, None)

        # olay şeridi
        items = []
        if rows:
            for r in sorted(rows, key=lambda x: x.event_id):
                R = r.response_us
                if r.status != "ok":
                    items.append((f"#{r.event_id} {r.status}", C["red"], r.status))
                elif R > DEADLINE_US:
                    items.append((f"#{r.event_id} {R / 1000:.1f}", C["amber"], "20 ms aşıldı"))
                else:
                    items.append((f"#{r.event_id} {R / 1000:.1f}", C["green"], "ok"))
        elif live:
            items = [(f"#{b.event_id} ⋯", C["violet"], "Butona basıldı — R kayıtlar gelince") for b in live]
        self.strip.set_items(items)
        self._set_stats(rows)
        self.cnt_tbl.setRowCount(len(counters))
        for i, (k, v) in enumerate(counters.items()):
            self.cnt_tbl.setItem(i, 0, QTableWidgetItem(str(k)))
            self.cnt_tbl.setItem(i, 1, QTableWidgetItem(str(v)))

    def _set_stats(self, rows):
        if not rows:
            for v in self.stats.values():
                v.setText("—")
                v.setStyleSheet("")
            return
        s = summarize(rows)
        lost = s["n_btn_drop"] + s["n_tx_drop"] + s["n_tx_error"] + s["n_timeout"]
        ovf = self.view_counters.get("log_overflow", self.view_counters.get("CNT.log_overflow", 0))

        def ms(v):
            return "—" if v is None else f"{v / 1000:.2f} ms"

        def put(key, text, bad=False, good=False):
            self.stats[key].setText(text)
            self.stats[key].setStyleSheet(f"color: {C['red']};" if bad else f"color: {C['green']};" if good else "")
        put("n", f"{s['n_ok']} / {s['n_events']}")
        put("med", ms(s["R_p50_us"]))
        put("p95", ms(s["R_p95_us"]))
        put("max", ms(s["R_max_us"]), bad=(s["R_max_us"] or 0) > DEADLINE_US)
        rate = s["n_met"] / s["n_events"] * 100 if s["n_events"] else 0
        put("met", f"%{rate:.0f}", bad=rate < 100, good=rate == 100)
        put("lost", f"{lost} · {ovf}", bad=bool(lost))
        m = s["margin_min_us"]
        put("margin", "—" if m is None else f"{m / 1000:+.2f} ms", bad=(m or 0) < 0, good=(m or 0) >= 0)

    def _on_event_clicked(self, eid: int):
        self.selected_event = eid
        self._last_key = None
        if self.view_label == LIVE:
            self._render_view(self.session.rows, self.session.counters, self.session.live_btn)
        else:
            self._render_view(self.view_rows, self.view_counters)

    # ============================================================ oturumlar
    def _refresh_sessions(self, select: str | None = None):
        self.sess_cb.blockSignals(True)
        cur = select or self.sess_cb.currentText() or LIVE
        self.sess_cb.clear()
        self.sess_cb.addItem(LIVE, None)
        for label, folder, sc in list_sessions(self.out_dir):
            self.sess_cb.addItem(label, (str(folder), sc))
        i = self.sess_cb.findText(cur)
        self.sess_cb.setCurrentIndex(max(0, i))
        self.sess_cb.blockSignals(False)
        self._on_session_selected()
        self.matrix.refresh()

    def _on_session_selected(self):
        data = self.sess_cb.currentData()
        self.view_label = self.sess_cb.currentText() or LIVE
        self.selected_event = None
        self._last_key = None
        if data is None:
            self._render_view(self.session.rows, self.session.counters, self.session.live_btn)
            return
        folder, sc = data
        rows, cnt = load_session(Path(folder), sc)
        self._render_view(rows, cnt)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Ölçüm klasörü", str(self.out_dir))
        if d:
            self.out_dir = Path(d)
            self._refresh_sessions()

    def _save(self):
        st = self.session
        try:
            paths = st.save(self.out_dir)
        except FileExistsError as exc:
            if QMessageBox.question(self, "Üzerine yaz",
                                    f"{exc} zaten var. Bu deneyle değiştirilsin mi?") != QMessageBox.Yes:
                return
            paths = st.save(self.out_dir, overwrite=True)
        except RuntimeError as exc:
            self._note(str(exc))
            return
        self._note(f"Kaydedildi: {paths[0].relative_to(self.out_dir)} (+ sayaçlar, ham oturum).")
        self._refresh_sessions(select=f"{st.variant} / {st.source} · {st.scenario}")

    def closeEvent(self, e):
        if self.worker:
            self.worker.stop()
        self.cmds.q.put((None, None, 0))
        super().closeEvent(e)


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
