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


@dataclass
class Btn:
    event_id: int
    scenario: str
    text: str


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
            return Tel(int(parts[1]), parts[2], int(parts[3]), int(parts[4]), int(parts[5]))
        if tag == "BTN":
            if len(parts) < 4:
                raise ProtocolError(f"BTN alan sayısı: {line!r}")
            return Btn(int(parts[1]), parts[2], parts[3])
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
        if tag in ("ACK", "NAK", "END", "BOOT"):
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


CMD_START = b"START\n"
CMD_STOP = b"STOP\n"
CMD_DUMP = b"DUMP\n"
CMD_INFO = b"INFO\n"
CMD_PING = b"PING\n"
