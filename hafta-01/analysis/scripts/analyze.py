"""Ham ölçümlerden özet tablo ve grafikleri üretir. Grafikler YALNIZCA ham CSV'den çizilir.

Girdi (measurements/):
  S0.csv … S5.csv            — her satır bir buton olayı (MCU zaman damgaları, µs)
  S*_counters.csv            — MCU sayaçları (kayıp, hata, periyot, CPU işi)
  raw/S*_session.log         — ham UART dökümü (faz analizi için TEL t_us)

Çıktı:
  measurements/summary.csv
  analysis/plots/R_vs_event.png        (zorunlu grafik 1)
  analysis/plots/stages_stacked.png    (zorunlu grafik 2)
  analysis/plots/stages_box.png
  analysis/plots/R_vs_phase.png        (hipotez testi: gecikme telemetri fazına bağlı mı?)
  analysis/results_tables.md           (report.md'nin kullandığı tablolar)

Çalıştırma:  python analysis/scripts/analyze.py [--measurements DIR] [--out DIR]
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
sys.path.insert(0, str(ROOT / "analysis" / "model"))
from uart_monitor.metrics import DEADLINE_US, STAGES, diff_us, read_counters, read_csv, summarize  # noqa: E402

SCENARIOS = ["S0", "S1", "S2", "S3", "S4", "S5"]
PERIOD_US = {"S1": 100_000, "S2": 20_000, "S3": 10_000, "S4": 10_000, "S5": 10_000}
STAGE_COLORS = ["#a78bfa", "#fbbf24", "#60a5fa", "#34d399"]
COUNTER_KEYS = ["accepted", "logged", "bounce_rejected", "ignored", "btn_q_drop", "btn_tx_drop",
                "tel_sent", "tel_tx_drop", "tx_error", "tx_timeout", "log_overflow", "fmt_error",
                "tel_period_min_us", "tel_period_max_us", "work_min_us", "work_max_us"]


def load(mdir: Path):
    data = {}
    for s in SCENARIOS:
        p = mdir / f"{s}.csv"
        if p.exists():
            data[s] = (read_csv(p), read_counters(mdir / f"{s}_counters.csv"))
    return data


def ms(v):
    return None if v is None else v / 1000.0


def write_summary(data, path: Path):
    rows = []
    for s, (events, cnt) in data.items():
        sm = summarize(events)
        row = {"scenario": s}
        for k, v in sm.items():
            if k == "scenario":
                continue
            row[k.replace("_us", "_ms")] = ms(v) if k.endswith("_us") else v
        for k in COUNTER_KEYS:
            row[f"mcu_{k}"] = cnt.get(f"CNT.{k}", "")
        row["fw"] = cnt.get("INF.fw", "")
        row["git"] = cnt.get("INF.git", "")
        row["build"] = cnt.get("INF.build", "")
        rows.append(row)
    if not rows:
        return rows
    with open(path, "w", newline="", encoding="ascii") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else ("" if v is None else v))
                        for k, v in r.items()})
    return rows


def plot_R_vs_event(data, out: Path):
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5), sharey=False)
    for ax, s in zip(axes.flat, SCENARIOS):
        if s not in data:
            ax.set_title(f"{s} — veri yok")
            ax.axis("off")
            continue
        ev = sorted(data[s][0], key=lambda r: r.event_id)
        ok = [(r.event_id, r.response_us / 1000) for r in ev if r.status == "ok"]
        bad = [(r.event_id, r.status) for r in ev if r.status != "ok"]
        if ok:
            x, y = zip(*ok)
            ax.plot(x, y, "o-", ms=4, lw=1, color="#2563eb", label="R (ok)")
        if bad:
            ax.plot([b[0] for b in bad], [0] * len(bad), "x", color="#dc2626", ms=8,
                    label="kayıp/hata (R yok)")
        ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1.2, label="D = 20 ms")
        late = sum(1 for _, v in ok if v * 1000 > DEADLINE_US)
        ax.set_title(f"{s}: n={len(ev)}, ok={len(ok)}, geç={late}, kayıp/hata={len(bad)}", fontsize=10)
        ax.set_xlabel("event_id")
        ax.set_ylabel("R = t4 − t0 (ms)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="upper left")
    fig.suptitle("Olay numarası → yanıt süresi (MCU TIM2, 1 µs çözünürlük). Kayıp yanıtlar R hesabına girmez, "
                 "'karşılandı' sayılmaz.", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "R_vs_event.png", dpi=130)
    plt.close(fig)


def plot_stages_stacked(data, out: Path, predictions: dict | None):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    xs = [s for s in SCENARIOS if s in data]
    bottoms = [0.0] * len(xs)
    for (label, i, j, _), color in zip(STAGES, STAGE_COLORS):
        vals = []
        for s in xs:
            ok = [r for r in data[s][0] if r.status == "ok"]
            v = [r.stage_us(i, j) for r in ok]
            vals.append(sum(v) / len(v) / 1000 if v else 0.0)
        ax.bar(xs, vals, bottom=bottoms, color=color, label=label, width=0.6)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    for x, b, s in zip(xs, bottoms, xs):
        n = sum(1 for r in data[s][0] if r.status == "ok")
        ax.text(x, b, f"{b:.2f} ms · n={n}", ha="center", va="bottom", fontsize=8)
    if predictions:
        px = [s for s in xs if s in predictions]
        ax.scatter(px, [predictions[s] for s in px], marker="D", color="black", zorder=5,
                   label="model: ort. R (tek basış)")
    ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1, label="D = 20 ms")
    ax.set_ylabel("ortalama süre (ms), yalnız status=ok")
    ax.set_title("Senaryo → aşamaların ortalama süreleri (yığılmış)", fontsize=11)
    ax.legend(fontsize=8, ncol=3)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "stages_stacked.png", dpi=130)
    plt.close(fig)


def plot_stages_box(data, out: Path):
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.2))
    xs = [s for s in SCENARIOS if s in data]
    for ax, (label, i, j, desc) in zip(axes, STAGES):
        series = []
        for s in xs:
            v = [r.stage_us(i, j) / 1000 for r in data[s][0] if r.status == "ok"]
            series.append(v if v else [float("nan")])
        ax.boxplot(series, tick_labels=xs, showfliers=True)
        for k, v in enumerate(series, start=1):
            ax.plot([k] * len(v), v, ".", alpha=0.35, color="#334155", ms=3)
        ax.set_title(f"{label}\n{desc}", fontsize=8)
        ax.set_ylabel("ms")
        ax.grid(alpha=0.3)
    fig.suptitle("Aşama dağılımları (her nokta bir olay): hangi aşama senaryoyla değişiyor?", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "stages_box.png", dpi=130)
    plt.close(fig)


def tel_times(raw_log: Path) -> list[int]:
    """Ham UART dökümünden TEL oluşturma anları (MCU saati)."""
    out = []
    if not raw_log.exists():
        return out
    for line in raw_log.read_text(encoding="ascii", errors="replace").splitlines():
        if line.startswith("#"):
            continue
        payload = line.split("\t", 1)[-1]
        if payload.startswith("TEL,"):
            parts = payload.split(",")
            try:
                out.append(int(parts[3]))
            except (IndexError, ValueError):
                pass
    return out


def plot_R_vs_phase(data, mdir: Path, out: Path):
    """t0'ın, kendisinden önceki son TEL üretim anına göre fazı. İki zaman da MCU saatidir."""
    xs = [s for s in ("S1", "S2", "S3", "S4", "S5") if s in data]
    if not xs:
        return False
    fig, axes = plt.subplots(1, len(xs), figsize=(4 * len(xs), 3.8), squeeze=False)
    drew = False
    for ax, s in zip(axes[0], xs):
        tels = sorted(tel_times(mdir / "raw" / f"{s}_session.log"))
        pts = []
        for r in data[s][0]:
            if r.status != "ok" or not tels:
                continue
            before = [t for t in tels if diff_us(t, r.t[0]) < PERIOD_US[s]]
            if not before:
                continue
            ph = min(diff_us(t, r.t[0]) for t in before)
            pts.append((ph / 1000, r.response_us / 1000))
        if pts:
            drew = True
            ax.plot(*zip(*pts), "o", ms=4)
        ax.axhline(DEADLINE_US / 1000, color="#dc2626", ls="--", lw=1)
        ax.set_title(f"{s}: n={len(pts)}", fontsize=9)
        ax.set_xlabel("t0 − son TEL üretimi (ms)")
        ax.set_ylabel("R (ms)")
        ax.grid(alpha=0.3)
    fig.suptitle("Faz analizi: R, basışın telemetri döngüsündeki konumuna bağlı mı?", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "R_vs_phase.png", dpi=130)
    plt.close(fig)
    return drew


def write_tables(rows, path: Path):
    def f(v, d=2):
        return "—" if v in (None, "") else (f"{v:.{d}f}" if isinstance(v, float) else str(v))

    lines = ["<!-- Bu dosya analysis/scripts/analyze.py tarafından üretilir. Elle düzenlemeyin. -->", "",
             "### Yanıt süresi (ms) — yalnız status=ok", "",
             "| Senaryo | olay | ok | deadline karşılandı | 20 ms'yi aşan | R min | R ort. | R p95 | R gözlenen maks. | min pay |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['n_events']} | {r['n_ok']} | {r['n_met']} | {r['n_late']} | "
                     f"{f(r['R_min_ms'])} | {f(r['R_mean_ms'])} | {f(r['R_p95_ms'])} | {f(r['R_max_ms'])} | "
                     f"{f(r['margin_min_ms'])} |")
    lines += ["", "### Aşama ortalamaları (ms) — yalnız status=ok", "",
              "| Senaryo | t1−t0 | t2−t1 | t3−t2 | t4−t3 | t1−t0 maks | t3−t2 maks |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {f(r['t1_t0_mean_ms'], 3)} | {f(r['t2_t1_mean_ms'], 3)} | "
                     f"{f(r['t3_t2_mean_ms'], 3)} | {f(r['t4_t3_mean_ms'], 3)} | {f(r['t1_t0_max_ms'], 3)} | "
                     f"{f(r['t3_t2_max_ms'], 3)} |")
    lines += ["", "### Kayıplar ve MCU sayaçları", "",
              "| Senaryo | btn_drop | tx_drop | tx_error | timeout | log_overflow | bounce | TEL gönderilen | TEL drop | "
              "periyot min–maks (µs) | CPU işi min–maks (µs) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['n_btn_drop']} | {r['n_tx_drop']} | {r['n_tx_error']} | "
                     f"{r['n_timeout']} | {r['mcu_log_overflow']} | {r['mcu_bounce_rejected']} | {r['mcu_tel_sent']} | "
                     f"{r['mcu_tel_tx_drop']} | {r['mcu_tel_period_min_us']}–{r['mcu_tel_period_max_us']} | "
                     f"{r['mcu_work_min_us']}–{r['mcu_work_max_us']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_predictions():
    p = ROOT / "analysis" / "model" / "predictions.csv"
    if not p.exists():
        return None
    with open(p, newline="") as f:
        return {r["scenario"]: float(r["R_mean_ms"]) for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measurements", type=Path, default=ROOT / "measurements")
    ap.add_argument("--out", type=Path, default=ROOT / "analysis")
    a = ap.parse_args()

    data = load(a.measurements)
    missing = [s for s in SCENARIOS if s not in data]
    if not data:
        print(f"Ölçüm bulunamadı: {a.measurements}. Önce arayüzle S0..S5 kaydedin.")
        return 1
    if missing:
        print("Eksik senaryolar:", ", ".join(missing))

    plots = a.out / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    rows = write_summary(data, a.measurements / "summary.csv")
    plot_R_vs_event(data, plots)
    plot_stages_stacked(data, plots, load_predictions())
    plot_stages_box(data, plots)
    phase = plot_R_vs_phase(data, a.measurements, plots)
    write_tables(rows, a.out / "results_tables.md")

    for r in rows:
        print(f"{r['scenario']}: n={r['n_events']} ok={r['n_ok']} geç={r['n_late']} "
              f"R ort/maks={r['R_mean_ms'] or 0:.2f}/{r['R_max_ms'] or 0:.2f} ms")
    print("Faz grafiği:", "çizildi" if phase else "TEL verisi yok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
