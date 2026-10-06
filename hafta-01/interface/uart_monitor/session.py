"""Deney oturumu: gelen satırları durumlara göre toplar ve diske yazar.

Deney sırası (her senaryoda aynı):
  1. VAR / SRC / EVN / SCN -> varyant, uyarım kaynağı, olay sayısı, senaryo
  2. START -> 5 s ısınma (MCU bu sürede basışları kabul etmez)
  3. N basış (fiziksel buton veya EXTI enjeksiyonu), aralarında >= 0,5 s
  4. N. olay kapanınca MCU otomatik STOP + DUMP yapar (ya da PC STOP/DUMP)
  5. LOG + CNT satırları -> CSV

Kayıt yeri: <ölçüm klasörü>/runs/<varyant>-<kaynak>/Sx.csv (+ _counters.csv, raw/).
Görevin resmî seti (A, fiziksel buton, 2026-09-27) <ölçüm klasörü>/Sx.csv olarak durur.
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
    IDLE = "Boşta"
    CONFIGURED = "Senaryo seçildi"
    WARMUP = "Isınma (5 s) — butona BASMAYIN"
    MEASURING = "Ölçüm sürüyor"
    STOPPING = "Durduruluyor (TX tamamlanıyor)"
    DUMPING = "Kayıtlar alınıyor"
    DONE = "Tamamlandı"


def run_dir(base: Path, variant: str, source: str) -> Path:
    return Path(base) / "runs" / f"{variant}-{source}"


@dataclass
class Session:
    scenario: Optional[str] = None
    variant: str = "A"
    source: str = "HW"
    target_n: int = MIN_PRESSES
    state: State = State.IDLE
    rows: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    raw: list = field(default_factory=list)          # (pc_zamanı, satır) — yalnız bilgi
    btn_seen: int = 0
    tel_seen: int = 0
    tel_gaps: int = 0                                # TEL sıra numarası boşlukları
    last_tel: Optional[P.Tel] = None
    prev_tel: Optional[P.Tel] = None
    last_btn: Optional[P.Btn] = None
    live_btn: list = field(default_factory=list)     # ölçüm sırasında gelen BTN'ler
    ext_test: Optional[tuple] = None                 # (n, min, ort, maks, sysclk)
    errors: list = field(default_factory=list)
    replies: list = field(default_factory=list)      # son komut yanıtları (komut el sıkışması)

    # ---- olaylar ----
    def _reset_run(self) -> None:
        self.rows.clear()
        self.counters.clear()
        self.errors.clear()
        self.live_btn.clear()
        self.btn_seen = self.tel_seen = self.tel_gaps = 0
        self.last_btn = self.last_tel = self.prev_tel = None

    def begin(self, scenario: str) -> None:
        self.scenario = scenario
        self.state = State.CONFIGURED
        self.raw.clear()
        self._reset_run()

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
            if self.last_tel is not None and msg.seq > self.last_tel.seq + 1:
                self.tel_gaps += msg.seq - self.last_tel.seq - 1
            self.tel_seen += 1
            self.prev_tel, self.last_tel = self.last_tel, msg
        elif isinstance(msg, P.Btn):
            self.btn_seen += 1
            self.last_btn = msg
            self.live_btn.append(msg)
        elif isinstance(msg, P.Log):
            self.rows.append(EventRow(msg.scenario, msg.event_id, msg.t, msg.status))
        elif isinstance(msg, P.KeyValue):
            (self.counters if msg.tag == "CNT" else self.info)[msg.key] = msg.value
            if msg.tag == "INF" and msg.key == "variant":
                self.variant = msg.value
            elif msg.tag == "INF" and msg.key == "source":
                self.source = msg.value
            elif msg.tag == "INF" and msg.key == "events":
                self.target_n = int(msg.value)
        elif isinstance(msg, P.Reply):
            self._on_reply(msg)

    def _on_reply(self, r: P.Reply) -> None:
        a = r.args
        self.replies.append(r)
        del self.replies[:-20]
        if r.tag == "ACK" and a[:1] == ["SCN"]:
            self.begin(a[1] if len(a) > 1 else self.scenario)
        elif r.tag == "ACK" and a[:1] == ["VAR"] and len(a) > 1:
            self.variant = a[1]
        elif r.tag == "ACK" and a[:1] == ["SRC"] and len(a) > 1:
            self.source = a[1]
        elif r.tag == "ACK" and a[:1] == ["EVN"] and len(a) > 1:
            self.target_n = int(a[1])
        elif r.tag == "ACK" and a[:1] == ["START"]:
            # ACK,START,<senaryo>[,<varyant>,<kaynak>,<n>]
            if len(a) > 1:
                self.scenario = a[1]
            if len(a) > 4:
                self.variant, self.source, self.target_n = a[2], a[3], int(a[4])
            self._reset_run()
            self.state = State.WARMUP
        elif r.tag == "ACK" and a[:1] == ["STOP"]:
            self.state = State.STOPPING
        elif r.tag == "END" and a[:1] == ["DUMP"]:
            self.state = State.DONE
        elif r.tag == "EXT" and len(a) >= 5:
            self.ext_test = tuple(int(x) for x in a[:5])
        elif r.tag == "NAK":
            self.errors.append("NAK: " + ",".join(a))

    # ---- canlı ölçümler ----
    def tel_period_us(self) -> Optional[int]:
        """Ardışık iki TEL'in MCU üretim anı farkı (gerçek periyot)."""
        if self.prev_tel and self.last_tel and self.last_tel.seq == self.prev_tel.seq + 1:
            return (self.last_tel.t_us - self.prev_tel.t_us) % (1 << 32)
        return None

    # ---- kayıt ----
    def target_dir(self, base: Path) -> Path:
        return run_dir(base, self.variant, self.source)

    def save(self, base: Path, overwrite: bool = False, flat: bool = False) -> list[Path]:
        """flat=True: doğrudan base/Sx.csv (görevin resmî düzeni). Aksi halde runs/<V>-<SRC>/."""
        if self.state is not State.DONE or not self.scenario:
            raise RuntimeError("Oturum tamamlanmadı (STOP + DUMP gerekli).")
        out_dir = Path(base) if flat else self.target_dir(base)
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
            info = dict(self.info)
            info["scenario"] = self.scenario      # bağlantı anındaki INFO eski senaryoyu taşıyabilir
            info["variant"] = self.variant
            info["source"] = self.source
            info["events"] = self.target_n
            info["saved_at"] = dt.datetime.now().isoformat(timespec="seconds")
            for k, v in info.items():
                w.writerow(["INF", k, v])
            for k, v in self.counters.items():
                w.writerow(["CNT", k, v])

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, "w", encoding="ascii", errors="replace", newline="\n") as f:
            f.write("# pc_rx_time yalnızca bilgi amaçlıdır; gecikme hesabında KULLANILMAZ.\n")
            for t, line in self.raw:
                f.write(f"{t}\t{line}\n")
        return [csv_path, cnt_path, raw_path]
