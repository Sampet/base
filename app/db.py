from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from app.models import Event, EventAnalytics, PricePoint


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._events: Dict[str, Event] = {}

    def upsert(self, event: Event) -> None:
        self._events[event.event_id] = event

    def get(self, event_id: str) -> Optional[Event]:
        return self._events.get(event_id)

    def list_by_category(self, category: str) -> List[Event]:
        return [event for event in self._events.values() if event.category == category]


class InMemoryPriceRepository:
    def __init__(self) -> None:
        self._prices: Dict[str, List[PricePoint]] = defaultdict(list)

    def add(self, price_point: PricePoint) -> None:
        self._prices[price_point.market_id].append(price_point)

    def list_for_market(self, market_id: str) -> List[PricePoint]:
        return list(self._prices.get(market_id, []))


class InMemoryAnalyticsRepository:
    def __init__(self) -> None:
        self._analytics: Dict[str, EventAnalytics] = {}

    def upsert(self, analytics: EventAnalytics) -> None:
        self._analytics[analytics.event_id] = analytics

    def get(self, event_id: str) -> Optional[EventAnalytics]:
        return self._analytics.get(event_id)


class RepositoryBundle:
    def __init__(self) -> None:
        self.events = InMemoryEventRepository()
        self.prices = InMemoryPriceRepository()
        self.analytics = InMemoryAnalyticsRepository()

    def list_prices_in_window(
        self,
        market_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> Iterable[PricePoint]:
        for price_point in self.prices.list_for_market(market_id):
            if start and price_point.timestamp < start:
                continue
            if end and price_point.timestamp > end:
                continue
            yield price_point
