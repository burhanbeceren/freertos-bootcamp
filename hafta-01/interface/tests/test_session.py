"""Oturum durum makinesi. Satırlar BİÇİM ÖRNEĞİDİR, ölçüm değildir."""
from uart_monitor.session import Session, State


def feed(s, *lines):
    for ln in lines:
        s.feed_line(ln)


def test_full_flow_and_save(tmp_path):
    s = Session()
    feed(s, "ACK,SCN,S3")
    assert s.state is State.CONFIGURED and s.scenario == "S3"
    feed(s, "ACK,START,S3")
    assert s.state is State.WARMUP
    feed(s, "TEL,1,S3,100,0,0".ljust(63), "BTN,1,S3,PRESSED".ljust(63))
    assert s.tel_seen == 1 and s.btn_seen == 1
    feed(s, "ACK,STOP,S3", "LOG,S3,1,10,20,30,40,5640,ok", "CNT,tel_tx_drop,0", "END,DUMP,S3")
    assert s.state is State.DONE and len(s.rows) == 1
    paths = s.save(tmp_path, flat=True)              # görevin resmî düzeni
    assert (tmp_path / "S3.csv").read_text().splitlines()[1] == "S3,1,10,20,30,40,5640,ok"
    paths2 = s.save(tmp_path)                        # varsayılan: runs/<V>-<SRC>/
    assert paths2[0] == tmp_path / "runs" / "A-HW" / "S3.csv"
    assert all(p.exists() for p in paths)


def test_nak_is_reported():
    s = Session()
    feed(s, "NAK,DUMP,running")
    assert s.errors and "NAK" in s.errors[0]
