"""PC -> kart komut kanalı.

İki yol vardır; ikisi de aynı komut metnini kartın komut işleyicisine (UartTxTask) ulaştırır:

* UART  : USB-TTL'nin TXD hattı -> PA3. Adaptörün TX'i çalışıyorsa kullanılır.
* SWD   : ST-LINK ile kartın RAM'indeki posta kutusuna (0x20000000) yazılır:
          16 bayt metin + 4 bayt sıra numarası (seq EN SON yazılır). Kart 100 ms'de bir
          yoklar. STM32CubeProgrammer CLI kullanılır (~0,1 s / komut).

Kanal seçimi otomatik: UART'tan PING gönderilir; 1 s içinde ACK,PING gelmezse SWD.
Kartın yanıtları her iki durumda da UART RX (kart -> PC) üzerinden gelir.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

MAILBOX_ADDR = 0x20000000

_CLI_CANDIDATES = [
    os.environ.get("STM32_PROGRAMMER_CLI", ""),
    r"C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe",
    r"C:/Program Files (x86)/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe",
    shutil.which("STM32_Programmer_CLI") or "",
]


def find_cli() -> Optional[str]:
    for c in _CLI_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


class SwdMailbox:
    """ST-LINK üzerinden posta kutusuna komut yazar."""

    def __init__(self, cli: Optional[str] = None, addr: int = MAILBOX_ADDR):
        self.cli = cli or find_cli()
        self.addr = addr
        self._seq = int(time.time() * 1000) & 0x7FFFFFFF
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.cli is not None

    def send(self, cmd: str) -> tuple[bool, str]:
        if not self.cli:
            return False, "STM32_Programmer_CLI bulunamadı"
        text = cmd.strip().encode("ascii")
        if len(text) > 15:
            return False, f"komut çok uzun: {cmd!r}"
        with self._lock:
            self._seq = (self._seq + 1) & 0xFFFFFFFF or 1
            words = struct.unpack("<4I", text.ljust(16, b"\0"))
            args = [self.cli, "-c", "port=SWD", "mode=HOTPLUG", "-w32", f"0x{self.addr:08X}"]
            args += [f"0x{w:08X}" for w in words] + [f"0x{self._seq:08X}"]
            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=10,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, str(exc)
        ok = out.returncode == 0 and "Error" not in out.stdout
        return ok, "" if ok else (out.stdout[-300:] or out.stderr[-300:])


class CommandChannel:
    """UART veya SWD. send(): komutu gönderir; yanıt (ACK/NAK) kartın UART çıkışından gelir.

    write_uart: seri porta bayt yazan fonksiyon (port açık değilse None).
    """

    def __init__(self, write_uart: Callable[[bytes], None] | None = None,
                 swd: Optional[SwdMailbox] = None):
        self.write_uart = write_uart
        self.swd = swd or SwdMailbox()
        self.mode: str = "swd" if self.swd.available else "uart"

    def describe(self) -> str:
        if self.mode == "uart":
            return "UART (PA3 ← TXD)"
        return "ST-LINK posta kutusu" if self.swd.available else "yok"

    def send(self, cmd: str) -> tuple[bool, str]:
        cmd = cmd.strip()
        if self.mode == "uart" and self.write_uart:
            self.write_uart((cmd + "\n").encode("ascii"))
            return True, ""
        return self.swd.send(cmd)


def wait_for(pred: Callable[[], bool], timeout: float, poll: float = 0.02) -> bool:
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if pred():
            return True
        time.sleep(poll)
    return pred()
