"""Metrik testleri. Değerler elle kurulmuş BİÇİM ÖRNEKLERİDİR, ölçüm değildir."""
from uart_monitor.metrics import EventRow, diff_us, read_csv, summarize, write_csv


def test_diff_wraps_mod_2_32():
    assert diff_us(0xFFFFFF00, 0x00000100) == 0x200
    assert diff_us(5, None) is None


def test_stages_and_R():
    r = EventRow("S3", 17, [1000000, 1002000, 1002300, 1004000, 1009606], "ok")
    assert r.response_us == 9606
    assert r.stage_us(0, 1) == 2000 and r.stage_us(3, 4) == 5606


def test_summary_counts_late_and_losses_separately():
    rows = [
        EventRow("S5", 1, [0, 10, 40, 50, 5600], "ok"),
        EventRow("S5", 2, [0, 10, 40, 50, 25000], "ok"),          # geç
        EventRow("S5", 3, [0, 10, 40, None, None], "tx_drop"),    # kayıp: karşılandı sayılmaz
    ]
    s = summarize(rows)
    assert s["n_events"] == 3 and s["n_ok"] == 2
    assert s["n_late"] == 1 and s["n_met"] == 1 and s["n_tx_drop"] == 1
    assert s["R_max_us"] == 25000 and s["margin_min_us"] == -5000


def test_csv_roundtrip_keeps_empty(tmp_path):
    rows = [EventRow("S3", 18, [1500000, 1502100, 1502400, None, None], "tx_drop")]
    p = tmp_path / "S3.csv"
    write_csv(p, rows)
    text = p.read_text()
    assert text.splitlines()[0] == "scenario,event_id,t0_us,t1_us,t2_us,t3_us,t4_us,status"
    assert text.splitlines()[1] == "S3,18,1500000,1502100,1502400,,,tx_drop"
    assert read_csv(p)[0].t[3] is None
