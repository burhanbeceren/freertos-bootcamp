"""Seri port okuma iş parçacığı. GUI donmaz; satırlar toplu sinyalle aktarılır."""
from __future__ import annotations

import datetime as dt
import threading

import serial
from PySide6.QtCore import QThread, Signal
from serial.tools import list_ports

BAUD = 115200


def available_ports() -> list[tuple[str, str]]:
    return [(p.device, f"{p.device} — {p.description}") for p in list_ports.comports()]


class SerialWorker(QThread):
    lines = Signal(list)          # [(pc_zamanı, satır), ...]
    failed = Signal(str)

    def __init__(self, port: str, baud: int = BAUD):
        super().__init__()
        self._port_name = port
        self._baud = baud
        self._ser: serial.Serial | None = None
        self._stop = threading.Event()
        self._wlock = threading.Lock()

    def run(self) -> None:
        try:
            self._ser = serial.Serial(self._port_name, self._baud, bytesize=8, parity="N",
                                      stopbits=1, timeout=0.05)
        except serial.SerialException as exc:
            self.failed.emit(str(exc))
            return
        buf = bytearray()
        try:
            while not self._stop.is_set():
                chunk = self._ser.read(self._ser.in_waiting or 1)
                if not chunk:
                    continue
                buf.extend(chunk)
                out = []
                while True:
                    i = buf.find(b"\n")
                    if i < 0:
                        break
                    line = bytes(buf[:i]).decode("ascii", errors="replace")
                    del buf[:i + 1]
                    out.append((dt.datetime.now().isoformat(timespec="milliseconds"), line))
                if out:
                    self.lines.emit(out)
        except serial.SerialException as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                self._ser.close()
            except Exception:
                pass

    def send(self, data: bytes) -> None:
        with self._wlock:
            if self._ser and self._ser.is_open:
                self._ser.write(data)

    def stop(self) -> None:
        self._stop.set()
        self.wait(1000)
