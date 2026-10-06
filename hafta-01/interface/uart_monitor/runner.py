"""Başlıksız deney yürütücüsü (arayüzle aynı protokol, oturum ve kayıt kodu).

Örnek: A/B/C x S0..S5, EXTI enjeksiyonu, her deneyde 50 olay
    python -m uart_monitor.runner --port COM5 --variants A,B,C --scenarios S0,S1,S2,S3,S4,S5 \
        --source INJ --events 50 --out ../measurements

Komutlar UART veya ST-LINK posta kutusu ile gider (--channel auto|uart|swd).
Fiziksel buton (--source HW) seçilirse kullanıcı basışlarını bekler.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import threading
import time
from pathlib import Path

import serial

from . import protocol as P
from .control import CommandChannel, wait_for
from .metrics import summarize
from .session import Session, State


class BoardLink:
    def __init__(self, port: str, channel: str = "auto"):
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.session = Session()
        self.replies: list[P.Reply] = []
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._buf = bytearray()
        self.th = threading.Thread(target=self._reader, daemon=True)
        self.th.start()
        self.chan = CommandChannel(write_uart=self.ser.write)
        if channel in ("auto", "uart"):
            self.chan.mode = "uart"
            if self.command("PING", "PING", timeout=1.0):
                return
            if channel == "uart":
                raise RuntimeError("UART üzerinden ACK,PING gelmedi")
        if not self.chan.swd.available:
            raise RuntimeError("PC -> kart kanalı yok (UART TX çalışmıyor, ST-LINK CLI bulunamadı)")
        self.chan.mode = "swd"
        if not self.command("PING", "PING", timeout=2.0):
            raise RuntimeError("ST-LINK posta kutusundan ACK,PING gelmedi")

    def _reader(self):
        while not self._stop.is_set():
            chunk = self.ser.read(self.ser.in_waiting or 1)
            if not chunk:
                continue
            self._buf.extend(chunk)
            while (i := self._buf.find(b"\n")) >= 0:
                line = bytes(self._buf[:i]).decode("ascii", "replace")
                del self._buf[:i + 1]
                with self.lock:
                    msg = self.session.feed_line(line, dt.datetime.now().isoformat(timespec="milliseconds"))
                    if isinstance(msg, P.Reply):
                        self.replies.append(msg)

    def command(self, cmd: str, key: str, timeout: float = 2.0) -> bool:
        """Komutu gönderir; ACK,<key> gelirse True, NAK veya zaman aşımında False."""
        with self.lock:
            start = len(self.replies)
        ok, err = self.chan.send(cmd)
        if not ok:
            print(f"  ! gönderilemedi {cmd}: {err}")
            return False

        def got():
            with self.lock:
                new = self.replies[start:]
            return any((r.tag in ("ACK", "NAK") and r.args[:1] == [key]) or
                       (r.tag == "ACK" and key in ("PING", "INFO") and r.args[:1] == [key]) or
                       (key == "EXT" and r.tag == "EXT") for r in new)
        if not wait_for(got, timeout):
            return False
        with self.lock:
            return not any(r.tag == "NAK" and r.args[:1] == [key] for r in self.replies[start:])

    def close(self):
        self._stop.set()
        self.th.join(1)
        self.ser.close()


def run_one(link: BoardLink, variant: str, scenario: str, source: str, n: int, out: Path) -> dict:
    s = link.session
    for cmd, key in ((f"VAR,{variant}", "VAR"), (f"SRC,{source}", "SRC"),
                     (f"EVN,{n}", "EVN"), (f"SCN,{scenario}", "SCN"), ("START", "START")):
        if not link.command(cmd, key, timeout=5.0):
            raise RuntimeError(f"{cmd}: yanıt yok / NAK ({s.errors[-1:] or ''})")
    timeout = 8.0 + n * (1.2 if source == "INJ" else 10.0) + 30.0
    if not wait_for(lambda: s.state is State.DONE, timeout, poll=0.2):
        link.command("STOP", "STOP", timeout=10.0)
        link.command("DUMP", "DUMP", timeout=10.0)
        wait_for(lambda: s.state is State.DONE, 15.0, poll=0.2)
    with link.lock:
        paths = s.save(out, overwrite=True)
        summ = summarize(s.rows)
        counters = dict(s.counters)
    return {"paths": paths, "summary": summ, "counters": counters}


def main(argv=None):
    ap = argparse.ArgumentParser(description="hafta-01 otomatik deney yürütücüsü")
    ap.add_argument("--port", required=True)
    ap.add_argument("--variants", default="A,B,C")
    ap.add_argument("--scenarios", default="S0,S1,S2,S3,S4,S5")
    ap.add_argument("--source", default="INJ", choices=["INJ", "HW"])
    ap.add_argument("--events", type=int, default=50)
    ap.add_argument("--channel", default="auto", choices=["auto", "uart", "swd"])
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "measurements")
    ap.add_argument("--exti-test", action="store_true", help="önce EXTI gecikme testini çalıştır")
    a = ap.parse_args(argv)

    link = BoardLink(a.port, a.channel)
    print(f"Komut kanalı: {link.chan.describe()}")
    try:
        if a.exti_test and link.command("EXTI", "EXT", timeout=5.0):
            n, mn, mean, mx, clk = link.session.ext_test
            ns = 1e9 / clk
            print(f"EXTI testi ({n} örnek): min {mn} / ort {mean} / maks {mx} çevrim = "
                  f"{mn * ns:.0f} / {mean * ns:.0f} / {mx * ns:.0f} ns")
        for v in a.variants.split(","):
            for sc in a.scenarios.split(","):
                t0 = time.time()
                res = run_one(link, v, sc, a.source, a.events, a.out)
                s, c = res["summary"], res["counters"]
                lost = s["n_btn_drop"] + s["n_tx_drop"] + s["n_tx_error"] + s["n_timeout"]
                print(f"{v}-{a.source} {sc}: n={s['n_events']} ok={s['n_ok']} geç={s['n_late']} kayıp={lost} "
                      f"R ort/maks={(s['R_mean_us'] or 0) / 1000:.2f}/{(s['R_max_us'] or 0) / 1000:.2f} ms "
                      f"TEL drop={c.get('tel_tx_drop', '?')}  ({time.time() - t0:.0f} s)", flush=True)
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
