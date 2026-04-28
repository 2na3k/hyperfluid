from dataclasses import dataclass


@dataclass
class Tick:
    source: str
    symbol: str
    stream_id: str
    price: float
    timestamp_ms: int
