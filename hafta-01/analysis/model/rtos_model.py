"""Olay-güdümlü zamanlama MODELİ (ölçüm DEĞİLDİR).

Amaç: ölçümden ÖNCE hipotez üretmek ve zaman çizelgesi çizmek. Model;
  - 3 görevli sabit öncelikli preemptive zamanlayıcıyı (3 > 2 > 1),
  - buton kuyruğunu (8) ve TX FIFO kuyruğunu (16),
  - UART hattını (64 bayt x 10 bit / 115200 = 5,556 ms),
  - TelemetryTask'taki ek CPU işini
temsil eder. Bağlam değişimi, HAL ve kopyalama maliyetleri aşağıdaki
Overheads varsayımlarıdır; gerçek değerler S0 ölçümünden alınıp güncellenmelidir.

Modelde bulunmayanlar: tick kesmesinin CPU payı, flash bekleme durumları,
kesme gecikmesi (NVIC), buton mekaniği. Bu yüzden çıktılar "tahmin"dir.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

LINE_US = 64 * 10 / 115200 * 1e6        # 5555.56 us: 64 bayt, 8N1
DEADLINE_US = 20_000.0
TXQ_LEN = 16
BTNQ_LEN = 8


@dataclass
class Overheads:
    """Varsayımlar (µs). S0 ölçümüyle kalibre edilecek."""
    isr_to_task: float = 10.0     # ISR -> ButtonTask'ın xQueueReceive'den dönmesi (t1 - t0, yüksüz)
    btn_prep: float = 15.0        # t2 - t1: BTN mesajını hazırlama
    btn_post: float = 5.0         # xQueueSend + tekrar bloklanma
    tel_fmt: float = 20.0         # TEL mesajı hazırlama + xQueueSend
    utx_pre: float = 8.0          # UartTxTask: kuyruktan alma -> t3
    tx_start: float = 20.0        # t4 - t3 - LINE: HAL DMA başlatma + TC ISR gözlemi
    utx_post: float = 8.0         # TC sonrası görevin kaydı kapatması


@dataclass
class Scenario:
    name: str
    period_us: Optional[float]    # None: telemetri kapalı
    work_us: float = 0.0


SCENARIOS = {
    "S0": Scenario("S0", None, 0),
    "S1": Scenario("S1", 100_000, 0),
    "S2": Scenario("S2", 20_000, 0),
    "S3": Scenario("S3", 10_000, 0),
    "S4": Scenario("S4", 10_000, 2_000),
    "S5": Scenario("S5", 10_000, 5_000),
}


@dataclass
class Event:
    id: int
    t: list = field(default_factory=lambda: [None] * 5)
    status: str = "pending"

    @property
    def R(self):
        return None if self.t[4] is None else self.t[4] - self.t[0]


@dataclass
class Msg:
    kind: str           # "TEL" / "BTN"
    ev: Optional[Event] = None


# --- görev istekleri --------------------------------------------------------
class Cpu:
    def __init__(self, d): self.d = d
class WaitUntil:
    def __init__(self, t): self.t = t
class WaitQ:
    def __init__(self, q): self.q = q
class WaitTC:
    pass


class Task:
    def __init__(self, name, prio, gen):
        self.name, self.prio, self.gen = name, prio, gen
        self.remaining = 0.0
        self.block = None          # None => çalışmaya hazır (adım bekliyor)

    def ready(self, sim) -> bool:
        b = self.block
        if b is None:
            return True
        if isinstance(b, WaitUntil):
            return sim.now >= b.t - 1e-9
        if isinstance(b, WaitQ):
            return len(b.q) > 0
        if isinstance(b, WaitTC):
            return sim.tc_flag
        return False


class Sim:
    def __init__(self, sc: Scenario, presses: list, oh: Overheads = Overheads(),
                 t_end: Optional[float] = None, t_start_tel: float = 0.0):
        self.sc, self.oh = sc, oh
        self.now = 0.0
        self.presses = deque(sorted(presses))
        self.t_end = t_end if t_end is not None else (max(presses) + 300_000 if presses else 100_000)
        self.btnq: deque = deque()
        self.txq: deque = deque()
        self.events: list[Event] = []
        self.tc_time: Optional[float] = None
        self.tc_flag = False
        self.cpu_log: list = []        # (task, start, end)
        self.line_log: list = []       # (kind, event_id, start, end)
        self.tel_drops = 0
        self.t_start_tel = t_start_tel
        self.tasks = [
            Task("TelemetryTask", 3, self._tel()),
            Task("ButtonTask", 2, self._btn()),
            Task("UartTxTask", 1, self._utx()),
        ]

    # --- görev gövdeleri (generator) ---
    def _tel(self):
        if self.sc.period_us is None:
            yield WaitUntil(float("inf"))
        k = 0
        while True:
            yield WaitUntil(self.t_start_tel + k * self.sc.period_us)
            yield Cpu(self.sc.work_us + self.oh.tel_fmt)
            if len(self.txq) < TXQ_LEN:
                self.txq.append(Msg("TEL"))
            else:
                self.tel_drops += 1
            k += 1

    def _btn(self):
        while True:
            yield WaitQ(self.btnq)
            ev = self.btnq.popleft()
            yield Cpu(self.oh.isr_to_task)
            ev.t[1] = self.now
            yield Cpu(self.oh.btn_prep)
            ev.t[2] = self.now
            if len(self.txq) < TXQ_LEN:
                self.txq.append(Msg("BTN", ev))
            else:
                ev.status = "tx_drop"
            yield Cpu(self.oh.btn_post)

    def _utx(self):
        while True:
            yield WaitQ(self.txq)
            m = self.txq.popleft()
            yield Cpu(self.oh.utx_pre)
            t3 = self.now
            if m.ev:
                m.ev.t[3] = t3
            self.tc_flag = False
            self.tc_time = t3 + self.oh.tx_start + LINE_US
            self.line_log.append((m.kind, m.ev.id if m.ev else None, t3 + self.oh.tx_start / 2, self.tc_time))
            self._tx_msg = m
            yield WaitTC()
            if m.ev:
                m.ev.status = "ok"
            yield Cpu(self.oh.utx_post)

    # --- dış olaylar ---
    def _next_external(self) -> float:
        c = [self.t_end]
        if self.presses:
            c.append(self.presses[0])
        if self.tc_time is not None:
            c.append(self.tc_time)
        for t in self.tasks:
            if isinstance(t.block, WaitUntil) and t.block.t > self.now + 1e-9:
                c.append(t.block.t)
        return min(c)

    def _process_external(self):
        while self.presses and self.presses[0] <= self.now + 1e-9:
            p = self.presses.popleft()
            ev = Event(len(self.events) + 1)
            ev.t[0] = p
            self.events.append(ev)
            if len(self.btnq) < BTNQ_LEN:
                self.btnq.append(ev)
            else:
                ev.status = "btn_drop"
        if self.tc_time is not None and self.tc_time <= self.now + 1e-9:
            m = self._tx_msg
            if m.ev:
                m.ev.t[4] = self.tc_time         # TC ISR: görevden bağımsız, anında
            self.tc_flag = True
            self.tc_time = None

    def run(self) -> "Sim":
        while self.now < self.t_end:
            self._process_external()
            ready = [t for t in self.tasks if t.ready(self)]
            if not ready:
                self.now = self._next_external()
                continue
            t = max(ready, key=lambda x: x.prio)
            if t.remaining > 1e-9:
                run = min(t.remaining, self._next_external() - self.now)
                if run <= 1e-9:
                    run = t.remaining if self._next_external() <= self.now + 1e-9 else run
                    self._process_external()
                    if run <= 1e-9:
                        continue
                self.cpu_log.append((t.name, self.now, self.now + run))
                t.remaining -= run
                self.now += run
                continue
            t.block = None
            req = next(t.gen)
            if isinstance(req, Cpu):
                t.remaining = req.d
            else:
                t.block = req
                if isinstance(req, WaitTC):
                    self.tc_flag = False
        return self


# --- yardımcılar -------------------------------------------------------------
def single_press(name: str, phase_us: float, warm_periods: int = 20, oh: Overheads = Overheads()):
    """Kararlı durumda, telemetri periyodunun `phase_us` anında tek basış."""
    sc = SCENARIOS[name]
    T = sc.period_us or 10_000
    t0 = warm_periods * T + phase_us
    sim = Sim(sc, [t0], oh, t_end=t0 + 250_000).run()
    return sim, sim.events[0]


def phase_sweep(name: str, step_us: float = 50.0, oh: Overheads = Overheads()):
    sc = SCENARIOS[name]
    T = sc.period_us or 10_000
    out = []
    ph = 0.0
    while ph < T:
        _, ev = single_press(name, ph, oh=oh)
        out.append((ph, ev))
        ph += step_us
    return out


def press_series(name: str, n: int = 30, gap_us: float = 500_000, seed: int = 1,
                 oh: Overheads = Overheads()):
    """Gerçek deney düzenine benzer: 5 s ısınma, sonra n basış, aralar >= 0,5 s ve değişken."""
    import random
    rnd = random.Random(seed)
    t = 5_000_000.0
    presses = []
    for _ in range(n):
        t += gap_us + rnd.uniform(0, 400_000)
        presses.append(t)
    sim = Sim(SCENARIOS[name], presses, oh, t_end=presses[-1] + 1_000_000).run()
    return sim
