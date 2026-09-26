"""Deney oturumu: gelen satırları durumlara göre toplar ve diske yazar.

Deney sırası (her senaryoda aynı):
  1. SCN   -> önceki TX biter, kayıt + sayaçlar sıfırlanır
  2. START -> 5 s ısınma (MCU bu sürede basışları kabul etmez)
  3. >= 30 basış, aralarında >= 0,5 s
  4. STOP  -> telemetri durur, TX tamamlanır / timeout kaydedilir
  5. DUMP  -> LOG + CNT satırları -> CSV
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from . import protocol as P
from .metrics import EventRow, write_csv

MIN_PRESSES = 30
WARMUP_S = 5.0


class State(Enum):
    IDLE = "Bağlı değil / boşta"
    CONFIGURED = "Senaryo seçildi"
    WARMUP = "Isınma (5 s) — butona BASMAYIN"
    MEASURING = "Ölçüm — butona basın (>= 30, aralarında >= 0,5 s)"
    STOPPING = "Durduruluyor (TX tamamlanıyor)"
    DUMPING = "Kayıtlar alınıyor"
    DONE = "Tamamlandı — kaydedilebilir"


@dataclass
class Session:
    scenario: Optional[str] = None
    state: State = State.IDLE
    rows: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    raw: list = field(default_factory=list)          # (pc_zamanı, satır) — yalnız bilgi
    btn_seen: int = 0
    tel_seen: int = 0
    last_tel: Optional[P.Tel] = None
    last_btn: Optional[P.Btn] = None
    errors: list = field(default_factory=list)
    start_monotonic: Optional[float] = None

    # ---- olaylar ----
    def begin(self, scenario: str) -> None:
        self.scenario = scenario
        self.state = State.CONFIGURED
        self.rows.clear()
        self.counters.clear()
        self.raw.clear()
        self.errors.clear()
        self.btn_seen = self.tel_seen = 0
        self.last_btn = self.last_tel = None

    def feed_line(self, line: str, pc_time: Optional[str] = None):
        """Satırı işler ve çözülmüş mesajı döner (veya None)."""
        self.raw.append((pc_time or dt.datetime.now().isoformat(timespec="milliseconds"), line))
        try:
            msg = P.parse_line(line)
        except P.ProtocolError as exc:
            self.errors.append(str(exc))
            return None
        self.feed(msg)
        return msg

    def feed(self, msg) -> None:
        if isinstance(msg, P.Tel):
            self.tel_seen += 1
            self.last_tel = msg
        elif isinstance(msg, P.Btn):
            self.btn_seen += 1
            self.last_btn = msg
        elif isinstance(msg, P.Log):
            self.rows.append(EventRow(msg.scenario, msg.event_id, msg.t, msg.status))
        elif isinstance(msg, P.KeyValue):
            (self.counters if msg.tag == "CNT" else self.info)[msg.key] = msg.value
        elif isinstance(msg, P.Reply):
            self._on_reply(msg)

    def _on_reply(self, r: P.Reply) -> None:
        a = r.args
        if r.tag == "ACK" and a[:1] == ["SCN"]:
            self.begin(a[1] if len(a) > 1 else self.scenario)
        elif r.tag == "ACK" and a[:1] == ["START"]:
            # MCU START'ta kayıt ve sayaçları sıfırlar; PC tarafı da aynı şeyi yapar.
            if len(a) > 1:
                self.scenario = a[1]
            self.rows.clear()
            self.counters.clear()
            self.errors.clear()
            self.btn_seen = self.tel_seen = 0
            self.last_btn = self.last_tel = None
            self.state = State.WARMUP
        elif r.tag == "ACK" and a[:1] == ["STOP"]:
            self.state = State.STOPPING
        elif r.tag == "END" and a[:1] == ["DUMP"]:
            self.state = State.DONE
        elif r.tag == "NAK":
            self.errors.append("NAK: " + ",".join(a))

    # ---- kayıt ----
    def save(self, out_dir: Path, overwrite: bool = False) -> list[Path]:
        if self.state is not State.DONE or not self.scenario:
            raise RuntimeError("Oturum tamamlanmadı (STOP + DUMP gerekli).")
        out_dir = Path(out_dir)
        csv_path = out_dir / f"{self.scenario}.csv"
        cnt_path = out_dir / f"{self.scenario}_counters.csv"
        raw_path = out_dir / "raw" / f"{self.scenario}_session.log"
        if not overwrite:
            for p in (csv_path, cnt_path, raw_path):
                if p.exists():
                    raise FileExistsError(p)

        rows = sorted(self.rows, key=lambda r: r.event_id)
        write_csv(csv_path, rows)

        with open(cnt_path, "w", newline="", encoding="ascii") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["group", "key", "value"])
            for k, v in self.info.items():
                w.writerow(["INF", k, v])
            for k, v in self.counters.items():
                w.writerow(["CNT", k, v])

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, "w", encoding="ascii", errors="replace") as f:
            f.write("# pc_rx_time yalnızca bilgi amaçlıdır; gecikme hesabında KULLANILMAZ.\n")
            for t, line in self.raw:
                f.write(f"{t}\t{line}\n")
        return [csv_path, cnt_path, raw_path]
