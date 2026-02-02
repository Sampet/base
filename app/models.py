from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str
    market_id: str
    title: str
    category: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    resolution: Optional[str] = None
    status: str = Field(default="active")


class PricePoint(BaseModel):
    market_id: str
    token_id: str
    timestamp: datetime
    price: float


class EventAnalytics(BaseModel):
    event_id: str
    min_price: Optional[float] = None
    min_price_time: Optional[datetime] = None
    max_price: Optional[float] = None
    max_price_time: Optional[datetime] = None
    last_price: Optional[float] = None
    last_price_time: Optional[datetime] = None
