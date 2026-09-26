"""Aşama süreleri ve senaryo özeti.

Tek doğruluk kaynağı: hem arayüz hem analysis/scripts bu modülü kullanır.
Tüm farklar MCU saatinden (TIM2, 1 MHz) ve mod 2^32 hesaplanır. Eksik zaman
0 kabul edilmez; o aşama hesaplanmaz.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

MOD = 1 << 32
DEADLINE_US = 20_000
CSV_HEADER = ["scenario", "event_id", "t0_us", "t1_us", "t2_us", "t3_us", "t4_us", "status"]

# (etiket, başlangıç indeksi, bitiş indeksi, açıklama)
STAGES = [
    ("t1-t0", 0, 1, "ISR -> görevin olayı alması (olay aktarımı + CPU beklemesi)"),
    ("t2-t1", 1, 2, "Yanıt hazırlama (preemption dahil olabilir)"),
    ("t3-t2", 2, 3, "Kuyruğa verme + TX FIFO bekleme + UART başlatma öncesi"),
    ("t4-t3", 3, 4, "UART başlatma + hat aktarımı + TC gözlemi"),
]


def diff_us(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """uint32 farkı, mod 2^32. Biri eksikse None."""
    if a is None or b is None:
        return None
    return (b - a) % MOD


@dataclass
class EventRow:
    scenario: str
    event_id: int
    t: list            # 5 eleman, eksik = None
    status: str

    @property
    def response_us(self) -> Optional[int]:
        """R = t4 - t0 (yalnızca t4 kaydedildiyse)."""
        return diff_us(self.t[0], self.t[4])

    def stage_us(self, i: int, j: int) -> Optional[int]:
        return diff_us(self.t[i], self.t[j])

    def to_csv(self) -> list:
        return [self.scenario, self.event_id] + ["" if v is None else v for v in self.t] + [self.status]


def read_csv(path: Path) -> list[EventRow]:
    rows = []
    with open(path, newline="", encoding="ascii") as f:
        rd = csv.reader(f)
        header = next(rd)
        if header != CSV_HEADER:
            raise ValueError(f"{path}: beklenmeyen başlık {header}")
        for r in rd:
            if not r:
                continue
            ts = [int(v) if v.strip() else None for v in r[2:7]]
            rows.append(EventRow(r[0], int(r[1]), ts, r[7]))
    return rows


def write_csv(path: Path, rows: Iterable[EventRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="ascii") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow(r.to_csv())


def read_counters(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    with open(path, newline="", encoding="ascii") as f:
        rd = csv.reader(f)
        next(rd, None)
        for r in rd:
            if len(r) >= 3:
                out[f"{r[0]}.{r[1]}"] = r[2]
    return out


def _pct(sorted_vals: list, p: float) -> Optional[float]:
    """Doğrusal enterpolasyonlu yüzdelik."""
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(sorted_vals[lo])
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _mean(vals: list) -> Optional[float]:
    return sum(vals) / len(vals) if vals else None


def summarize(rows: list[EventRow], deadline_us: int = DEADLINE_US) -> dict:
    """Bir senaryonun özeti. Yalnızca ortalama değil; min/max, geç yanıt ve kayıplar."""
    completed = [r for r in rows if r.status == "ok" and r.response_us is not None]
    R = sorted(r.response_us for r in completed)
    by_status = {s: sum(1 for r in rows if r.status == s) for s in
                 ("ok", "btn_drop", "tx_drop", "tx_error", "timeout", "pending")}
    late = sum(1 for v in R if v > deadline_us)

    s = {
        "scenario": rows[0].scenario if rows else "",
        "n_events": len(rows),
        "n_ok": len(completed),
        "n_met": len(completed) - late,   # kayıp yanıtlar "karşılandı" sayılmaz
        "n_late": late,
        **{f"n_{k}": v for k, v in by_status.items() if k != "ok"},
        "R_min_us": R[0] if R else None,
        "R_mean_us": _mean(R),
        "R_p50_us": _pct(R, 50),
        "R_p95_us": _pct(R, 95),
        "R_max_us": R[-1] if R else None,
        "margin_min_us": (deadline_us - R[-1]) if R else None,
    }
    for label, i, j, _ in STAGES:
        vals = sorted(v for v in (r.stage_us(i, j) for r in completed) if v is not None)
        key = label.replace("-", "_")
        s[f"{key}_mean_us"] = _mean(vals)
        s[f"{key}_min_us"] = vals[0] if vals else None
        s[f"{key}_max_us"] = vals[-1] if vals else None
    return s
