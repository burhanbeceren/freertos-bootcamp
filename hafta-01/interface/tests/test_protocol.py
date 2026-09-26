"""Protokol çözücü testleri. Satırlar BİÇİM ÖRNEĞİDİR, ölçüm sonucu değildir."""
import pytest

from uart_monitor import protocol as P


def pad64(s: str) -> str:
    assert len(s) <= 63
    return s.ljust(63) + "\n"


def test_tel_fixed_64():
    raw = pad64("TEL,1042,S3,123456,0,726")
    assert len(raw) == 64
    m = P.parse_line(raw)
    assert m == P.Tel(1042, "S3", 123456, 0, 726)


def test_btn():
    m = P.parse_line(pad64("BTN,17,S3,PRESSED"))
    assert m == P.Btn(17, "S3", "PRESSED")


def test_log_ok_and_missing_fields_are_none_not_zero():
    m = P.parse_line("LOG,S3,17,1000000,1002000,1002300,1004000,1009606,ok")
    assert m.t == [1000000, 1002000, 1002300, 1004000, 1009606] and m.status == "ok"
    m = P.parse_line("LOG,S3,18,1500000,1502100,1502400,,,tx_drop")
    assert m.t == [1500000, 1502100, 1502400, None, None] and m.status == "tx_drop"


def test_log_rejects_unknown_status():
    with pytest.raises(P.ProtocolError):
        P.parse_line("LOG,S3,1,1,2,3,4,5,great")


def test_kv_and_replies():
    assert P.parse_line("CNT,tel_tx_drop,3") == P.KeyValue("CNT", "tel_tx_drop", "3")
    assert P.parse_line("ACK,SCN,S2") == P.Reply("ACK", ["SCN", "S2"])
    assert P.parse_line("END,DUMP,S2") == P.Reply("END", ["DUMP", "S2"])


def test_commands():
    assert P.cmd_scenario("S5") == b"SCN,S5\n"
    with pytest.raises(ValueError):
        P.cmd_scenario("S9")
