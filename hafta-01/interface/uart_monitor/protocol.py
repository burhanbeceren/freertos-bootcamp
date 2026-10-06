"""MCU <-> PC satır protokolü (docs/protokol.md).

MCU -> PC satırları LF ile biter. TEL/BTN tam 64 bayttır (63 bayt ASCII + boşluk
dolgusu + LF); diğer satırlar değişken uzunlukludur ve yalnızca ölçüm dışında
gönderilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MSG_LEN = 64
STATUSES = ("ok", "btn_drop", "tx_drop", "tx_error", "timeout", "pending")
SCENARIOS = ("S0", "S1", "S2", "S3", "S4", "S5")


@dataclass
class Tel:
    seq: int
    scenario: str
    t_us: int          # MCU'da TEL oluşturma anı (TIM2)
    work_us: int       # Bu periyotta ölçülen CPU işi süresi
    chk: int
    txq: Optional[int] = None       # TX kuyruğu doluluğu (FW >= 1.1)
    temp_dC: Optional[int] = None   # Dahili sıcaklık, 0,1 °C (FW >= 1.1)
    vdda_mV: Optional[int] = None


@dataclass
class Btn:
    event_id: int
    scenario: str
    text: str
    t0: Optional[int] = None        # FW >= 1.1: canlı t0 / t1
    t1: Optional[int] = None


@dataclass
class Log:
    scenario: str
    event_id: int
    t: list            # [t0..t4], eksik olan None
    status: str


@dataclass
class KeyValue:
    tag: str           # "CNT" veya "INF"
    key: str
    value: str


@dataclass
class Reply:
    tag: str           # ACK / NAK / END / BOOT
    args: list = field(default_factory=list)


@dataclass
class Unknown:
    text: str


class ProtocolError(ValueError):
    pass


def _opt_int(s: str) -> Optional[int]:
    s = s.strip()
    return int(s) if s else None


def parse_line(raw: str):
    """Tek satırı çözer. Dolgu boşlukları ve CR/LF atılır."""
    line = raw.rstrip("\r\n").rstrip(" ")
    if not line:
        return None
    parts = line.split(",")
    tag = parts[0]
    try:
        if tag == "TEL":
            if len(parts) < 6:
                raise ProtocolError(f"TEL alan sayısı: {line!r}")
            ext = [int(x) for x in parts[6:9]]
            ext += [None] * (3 - len(ext))
            temp = ext[1] if ext[1] is not None and ext[1] > -9999 else None
            return Tel(int(parts[1]), parts[2], int(parts[3]), int(parts[4]), int(parts[5]),
                       ext[0], temp, ext[2] or None)
        if tag == "BTN":
            if len(parts) < 4:
                raise ProtocolError(f"BTN alan sayısı: {line!r}")
            t0 = int(parts[4]) if len(parts) > 5 else None
            t1 = int(parts[5]) if len(parts) > 5 else None
            return Btn(int(parts[1]), parts[2], parts[3], t0, t1)
        if tag == "LOG":
            if len(parts) != 9:
                raise ProtocolError(f"LOG alan sayısı: {line!r}")
            ts = [_opt_int(p) for p in parts[3:8]]
            status = parts[8]
            if status not in STATUSES:
                raise ProtocolError(f"Bilinmeyen durum: {status!r}")
            return Log(parts[1], int(parts[2]), ts, status)
        if tag in ("CNT", "INF"):
            if len(parts) < 3:
                raise ProtocolError(f"{tag} alan sayısı: {line!r}")
            return KeyValue(tag, parts[1], ",".join(parts[2:]))
        if tag in ("ACK", "NAK", "END", "BOOT", "EXT"):
            return Reply(tag, parts[1:])
    except ValueError as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError(f"Sayı çözülemedi: {line!r}") from exc
    return Unknown(line)


# ---- PC -> MCU komutları -----------------------------------------------------

def cmd_scenario(name: str) -> bytes:
    if name not in SCENARIOS:
        raise ValueError(name)
    return f"SCN,{name}\n".encode("ascii")


VARIANTS = ("A", "B", "C")
SOURCES = ("HW", "INJ")


def cmd_variant(v: str) -> bytes:
    if v not in VARIANTS:
        raise ValueError(v)
    return f"VAR,{v}\n".encode("ascii")


def cmd_source(src: str) -> bytes:
    if src not in SOURCES:
        raise ValueError(src)
    return f"SRC,{src}\n".encode("ascii")


def cmd_events(n: int) -> bytes:
    if not 1 <= n <= 128:
        raise ValueError(n)
    return f"EVN,{n}\n".encode("ascii")


CMD_EXTI = b"EXTI\n"
CMD_START = b"START\n"
CMD_STOP = b"STOP\n"
CMD_DUMP = b"DUMP\n"
CMD_INFO = b"INFO\n"
CMD_PING = b"PING\n"
