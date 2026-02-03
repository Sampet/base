from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


@dataclass
class Event:
    event_id: str
    market_id: str
    token_id: str
    title: str
    category: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    resolution: Optional[str] = None
    status: str = field(default="active")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["start_time"] = _serialize_datetime(self.start_time)
        payload["end_time"] = _serialize_datetime(self.end_time)
        return payload


@dataclass
class PricePoint:
    market_id: str
    token_id: str
    timestamp: datetime
    price: float

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["timestamp"] = _serialize_datetime(self.timestamp)
        return payload


@dataclass
class EventAnalytics:
    event_id: str
    min_price: Optional[float] = None
    min_price_time: Optional[datetime] = None
    max_price: Optional[float] = None
    max_price_time: Optional[datetime] = None
    last_price: Optional[float] = None
    last_price_time: Optional[datetime] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["min_price_time"] = _serialize_datetime(self.min_price_time)
        payload["max_price_time"] = _serialize_datetime(self.max_price_time)
        payload["last_price_time"] = _serialize_datetime(self.last_price_time)
        return payload
