"""A/B/C gecikme azaltma varyantlarını gerçek ölçümlerden karşılaştırır.

Girdi : measurements/runs/<V>-<KAYNAK>/S0..S5.csv (+ _counters.csv)
Çıktı : analysis/plots/variants_R.png, analysis/plots/variants_stages.png,
        analysis/variants_tables.md, measurements/variants_summary.csv

Çalıştırma:  python analysis/scripts/compare_variants.py [--source INJ|HW]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "interface"))
from uart_monitor.metrics import DEADLINE_US, STAGES, read_counters, read_csv, summarize  # noqa: E402

SCN = ["S0", "S1", "S2", "S3", "S4", "S5"]
VAR = ["A", "B", "C"]
VCOL = {"A": "#64748b", "B": "#3b82f6", "C": "#10b981"}
SCOL = ["#a78bfa", "#fbbf24", "#60a5fa", "#34d399"]
VDESC = {"A": "A: görev standardı (FIFO, Tel>Btn>Uart)",
         "B": "B: öncelikli yanıt kuyruğu",
         "C": "C: B + öncelik Btn>Uart>Tel"}


def load(mdir: Path, source: str):
    data = {}
    for v in VAR:
        d = mdir / "runs" / f"{v}-{source}"
        for s in SCN:
            p = d / f"{s}.csv"
            if p.exists():
                data[(v, s)] = (read_csv(p), read_counters(d / f"{s}_counters.csv"))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="INJ", choices=["INJ", "HW"])
    ap.add_argument("--measurements", type=Path, default=ROOT / "measurements")
    ap.add_argument("--out", type=Path, default=ROOT / "analysis")
    a = ap.parse_args()
    data = load(a.measurements, a.source)
    if not data:
        print("Varyant ölçümü yok:", a.measurements / "runs")
        return 1

    rows = []
    for v in VAR:
        for s in SCN:
            if (v, s) not in data:
                continue
            ev, cnt = data[(v, s)]
            sm = summarize(ev)
            lost = sm["n_btn_drop"] + sm["n_tx_drop"] + sm["n_tx_error"] + sm["n_timeout"]
            rows.append({
                "variant": v, "scenario": s, "source": a.source, "n_events": sm["n_events"], "n_ok": sm["n_ok"],
                "n_met": sm["n_met"], "n_late": sm["n_late"], "n_lost": lost,
                "R_mean_ms": (sm["R_mean_us"] or 0) / 1000, "R_p95_ms": (sm["R_p95_us"] or 0) / 1000,
                "R_max_ms": (sm["R_max_us"] or 0) / 1000,
                "margin_min_ms": None if sm["margin_min_us"] is None else sm["margin_min_us"] / 1000,
                **{f"{lab.replace('-', '_')}_mean_ms": (sm[f"{lab.replace('-', '_')}_mean_us"] or 0) / 1000
                   for lab, *_ in STAGES},
                "t1_t0_max_ms": (sm["t1_t0_max_us"] or 0) / 1000,
                "t3_t2_max_ms": (sm["t3_t2_max_us"] or 0) / 1000,
                "tel_sent": cnt.get("CNT.tel_sent", ""), "tel_drop": cnt.get("CNT.tel_tx_drop", ""),
                "work_max_us": cnt.get("CNT.work_max_us", ""),
            })

    with open(a.measurements / "variants_summary.csv", "w", newline="", encoding="ascii") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{x:.3f}" if isinstance(x, float) else ("" if x is None else x)) for k, x in r.items()})

    # --- Grafik 1: senaryo x varyant, ortalama (çubuk) + maks (▲), 20 ms
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.2), gridspec_kw={"width_ratios": [3, 2]})
    ax = axes[0]
    W = 0.26
    for i, v in enumerate(VAR):
        xs = [j + (i - 1) * W for j, s in enumerate(SCN) if (v, s) in data]
        rr = [r for r in rows if r["variant"] == v]
        ax.bar(xs, [r["R_mean_ms"] for r in rr], W, color=VCOL[v], label=VDESC[v])
        ax.scatter(xs, [r["R_max_ms"] for r in rr], marker="^", color=VCOL[v], edgecolor="black", zorder=5, s=36)
        for x, r in zip(xs, rr):
            if r["n_lost"]:
                ax.text(x, r["R_max_ms"] * 1.25, f"{r['n_lost']} kayıp", ha="center", fontsize=8,
                        color="#b91c1c", fontweight="bold")
    ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1.2, label="D = 20 ms")
    ax.set_xticks(range(len(SCN)), SCN)
    ax.set_yscale("log")
    ax.set_ylim(4, 400)
    ax.set_ylabel("R (ms, log) — çubuk: ortalama, ▲: gözlenen maks.")
    ax.set_title(f"Varyant karşılaştırması ({a.source}, gerçek kart, her deney {rows[0]['n_events']} olay)",
                 fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.3, which="both")

    ax = axes[1]
    for i, v in enumerate(VAR):
        rr = [r for r in rows if r["variant"] == v]
        ax.plot([SCN.index(r["scenario"]) for r in rr], [r["R_max_ms"] for r in rr], "o-",
                color=VCOL[v], label=f"{v}: maks")
    ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1.2)
    ax.set_xticks(range(len(SCN)), SCN)
    ax.set_ylim(0, 25)
    ax.set_ylabel("gözlenen maks. R (ms), 0–25 ms yakın görünüm")
    ax.set_title("Kayma: gözlenen en kötü yanıt", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    plots = a.out / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    fig.savefig(plots / "variants_R.png", dpi=130)
    plt.close(fig)

    # --- Grafik 2: S3, S4, S5 için aşama ortalamaları (yığılmış)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=False)
    for ax, s in zip(axes, ["S3", "S4", "S5"]):
        vs = [v for v in VAR if (v, s) in data]
        bottoms = [0.0] * len(vs)
        for k, (lab, *_r) in enumerate(STAGES):
            key = f"{lab.replace('-', '_')}_mean_ms"
            vals = [next(r[key] for r in rows if r["variant"] == v and r["scenario"] == s) for v in vs]
            ax.bar(vs, vals, bottom=bottoms, color=SCOL[k], label=lab if s == "S3" else None, width=0.55)
            bottoms = [b + x for b, x in zip(bottoms, vals)]
        cap = 22.0
        for x, b in zip(vs, bottoms):
            ax.text(x, min(b, cap), f"{b:.2f}" + (" ↑" if b > cap else ""), ha="center", va="bottom", fontsize=8)
        ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1)
        ax.set_ylim(0, cap + 2)
        ax.set_title(f"{s}: aşama ortalamaları (ms, yalnız ok)" +
                     (" — 22 ms'de kesildi" if max(bottoms) > cap else ""), fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plots / "variants_stages.png", dpi=130)
    plt.close(fig)

    # --- Tablo
    def f(x, d=2):
        return "—" if x in (None, "") else (f"{x:.{d}f}" if isinstance(x, float) else str(x))
    lines = ["<!-- analysis/scripts/compare_variants.py tarafından gerçek ölçümden üretilir. -->", "",
             f"Kaynak: **{a.source}**. Süreler ms. Yalnız `ok` olaylar R istatistiğine girer.", "",
             "| Varyant | Senaryo | ok/olay | R ort. | R p95 | **R maks** | 20 ms aşımı | kayıp | t₁−t₀ maks | "
             "t₃−t₂ ort. | t₃−t₂ maks | TEL düşen | min pay |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['variant']} | {r['scenario']} | {r['n_ok']}/{r['n_events']} | {f(r['R_mean_ms'])} | "
                     f"{f(r['R_p95_ms'])} | **{f(r['R_max_ms'])}** | {r['n_late']} | {r['n_lost']} | "
                     f"{f(r['t1_t0_max_ms'], 3)} | {f(r['t3_t2_mean_ms'], 3)} | {f(r['t3_t2_max_ms'], 3)} | "
                     f"{r['tel_drop']} | {f(r['margin_min_ms'])} |")
    (a.out / "variants_tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['variant']} {r['scenario']}: ok {r['n_ok']}/{r['n_events']} R ort/maks "
              f"{r['R_mean_ms']:.2f}/{r['R_max_ms']:.2f} geç {r['n_late']} kayıp {r['n_lost']} TELdrop {r['tel_drop']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
