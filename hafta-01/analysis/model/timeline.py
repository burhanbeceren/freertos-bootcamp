"""Üç senaryonun zaman çizelgesini (MODEL) ve tahmin tablolarını üretir.

Çıktılar:
  docs/zaman-cizelgesi.png / .svg     — S0, S3 (en kötü faz), S5 (en kötü faz)
  analysis/model/predictions.csv       — tüm senaryolar için faz taraması özeti
  analysis/model/s5_series.png         — S5'te art arda basışlarda birikme (MODEL)

Çalıştırma:  python analysis/model/timeline.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rtos_model import DEADLINE_US, LINE_US, Overheads, phase_sweep, press_series, single_press  # noqa: E402

ROOT = HERE.parents[1]
DOCS = ROOT / "docs"

ROWS = ["TelemetryTask (3)", "ButtonTask (2)", "UartTxTask (1)", "UART hattı"]
TASK_ROW = {"TelemetryTask": 0, "ButtonTask": 1, "UartTxTask": 2}
C_TASK = {"TelemetryTask": "#f59e0b", "ButtonTask": "#8b5cf6", "UartTxTask": "#0ea5e9"}
C_LINE = {"TEL": "#94a3b8", "BTN": "#10b981"}
C_STAGE = ["#c4b5fd", "#fde68a", "#93c5fd", "#6ee7b7"]
STAGE_NAMES = ["t1−t0 görev bekleme", "t2−t1 hazırlama", "t3−t2 TX öncesi", "t4−t3 UART + TC"]

CASES = [
    ("S0", 3_000.0, "S0 · telemetri kapalı (referans)"),
    ("S3", 0.0, "S3 · 100 Hz, basış TEL gönderimi başlarken (en kötü faz)"),
    ("S5", 100.0, "S5 · 100 Hz + 5 ms CPU, basış iş başlarken (en kötü faz, ilk basış)"),
]


def draw_case(ax, name, phase, title):
    sim, ev = single_press(name, phase)
    t0 = ev.t[0]
    lo, hi = t0 - 2_000, t0 + 23_000
    ms = lambda t: (t - t0) / 1000.0  # noqa: E731

    for task, s, e in sim.cpu_log:
        if e < lo or s > hi:
            continue
        r = TASK_ROW[task]
        ax.broken_barh([(ms(s), (e - s) / 1000)], (r - 0.35, 0.7), color=C_TASK[task])
    for kind, eid, s, e in sim.line_log:
        if e < lo or s > hi:
            continue
        mine = kind == "BTN" and eid == ev.id
        ax.broken_barh([(ms(s), (e - s) / 1000)], (3 - 0.35, 0.7),
                       color=C_LINE[kind] if mine or kind == "TEL" else "#a7f3d0",
                       edgecolor="black" if mine else "none", linewidth=1.2)
        ax.text(ms(s) + (e - s) / 2000, 3, kind if kind == "TEL" else f"BTN#{eid}",
                ha="center", va="center", fontsize=7, color="white" if kind == "TEL" else "black")

    # aşama çubuğu (ölçülen aralıklar)
    for k in range(4):
        a, b = ev.t[k], ev.t[k + 1]
        ax.broken_barh([(ms(a), (b - a) / 1000)], (4 - 0.3, 0.6), color=C_STAGE[k])
    for k, t in enumerate(ev.t):
        ax.axvline(ms(t), color="#334155", lw=0.6, ls=":")
        ax.text(ms(t), 4.55, f"t{k}", ha="center", fontsize=8, color="#334155")
    ax.axvline(DEADLINE_US / 1000, color="#dc2626", lw=1.5, ls="--")
    ax.text(DEADLINE_US / 1000 + 0.15, -0.55, "D = 20 ms", color="#dc2626", fontsize=8)

    R = ev.R
    margin = DEADLINE_US - R
    verdict = "karşılandı" if margin >= 0 else "KAÇIRILDI"
    stages = [ev.t[k + 1] - ev.t[k] for k in range(4)]
    ax.set_title(f"{title}\nR = {R / 1000:.2f} ms · pay = {margin / 1000:+.2f} ms ({verdict}) · "
                 f"aşamalar: " + " / ".join(f"{s / 1000:.2f}" for s in stages) + " ms",
                 fontsize=9, loc="left")
    ax.set_yticks(range(5), ROWS + ["Ölçülen aşamalar"])
    ax.set_ylim(-0.8, 4.9)
    ax.set_xlim(ms(lo), ms(hi))
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25)
    return name, ev, R, margin, stages


def timeline_figure():
    fig, axes = plt.subplots(3, 1, figsize=(12, 10.5), sharex=True)
    rows = [draw_case(ax, *c) for ax, c in zip(axes, CASES)]
    axes[-1].set_xlabel("ISR girişinden (t0) itibaren süre (ms)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in C_STAGE] + \
              [plt.Rectangle((0, 0), 1, 1, color=C_TASK[t]) for t in C_TASK] + \
              [plt.Rectangle((0, 0), 1, 1, color=C_LINE["TEL"]), plt.Rectangle((0, 0), 1, 1, color=C_LINE["BTN"])]
    labels = STAGE_NAMES + ["TelemetryTask CPU", "ButtonTask CPU", "UartTxTask CPU", "TEL hatta", "BTN hatta"]
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("MODEL TAHMİNİ — ölçüm değildir. 64 B × 10 bit / 115200 = 5,556 ms hat süresi; "
                 "ek yükler rtos_model.Overheads varsayımıdır.", fontsize=9, color="#b45309")
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    for ext in ("png", "svg"):
        fig.savefig(DOCS / f"zaman-cizelgesi.{ext}", dpi=130)
    plt.close(fig)
    return rows


def predictions_table():
    out = []
    for name in ("S0", "S1", "S2", "S3", "S4", "S5"):
        sw = phase_sweep(name, step_us=25 if name != "S1" else 100)
        R = [ev.R for _, ev in sw]
        st = [[ev.t[k + 1] - ev.t[k] for k in range(4)] for _, ev in sw]
        miss = sum(r > DEADLINE_US for r in R)
        row = {
            "scenario": name,
            "R_min_ms": min(R) / 1000, "R_mean_ms": sum(R) / len(R) / 1000, "R_max_ms": max(R) / 1000,
            "margin_min_ms": (DEADLINE_US - max(R)) / 1000,
            "miss_fraction_single_press": miss / len(R),
        }
        for k, lab in enumerate(["t1_t0", "t2_t1", "t3_t2", "t4_t3"]):
            vals = [s[k] for s in st]
            row[f"{lab}_mean_ms"] = sum(vals) / len(vals) / 1000
            row[f"{lab}_max_ms"] = max(vals) / 1000
        out.append(row)
    with open(HERE / "predictions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        for r in out:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v) for k, v in r.items()})
    return out


def s5_series_figure():
    sim = press_series("S5", n=30)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ok = [(e.id, e.R / 1000) for e in sim.events if e.R is not None]
    bad = [e.id for e in sim.events if e.R is None]
    ax.plot(*zip(*ok), "o-", ms=4, label="R (model)")
    if bad:
        ax.plot(bad, [0] * len(bad), "rx", label="tx_drop (model)")
    ax.axhline(20, color="#dc2626", ls="--", label="D = 20 ms")
    ax.set_xlabel("event_id")
    ax.set_ylabel("R (ms)")
    ax.set_title("MODEL — S5'te art arda basışlar: UartTxTask aç kaldığı için TX kuyruğu birikir", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(HERE / "s5_series.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    print(f"LINE_US = {LINE_US:.1f}")
    print("Overheads:", Overheads())
    for name, ev, R, m, st in timeline_figure():
        print(f"{name}: R={R / 1000:.3f} ms margin={m / 1000:+.3f} ms stages(ms)="
              + ", ".join(f"{s / 1000:.3f}" for s in st))
    for r in predictions_table():
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    s5_series_figure()
