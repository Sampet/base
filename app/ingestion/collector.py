from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List

from app.clients.gamma import GammaClient
from app.config import settings
from app.db import RepositoryBundle
from app.models import Event


class EventCollector:
    def __init__(self, repositories: RepositoryBundle, gamma: GammaClient | None = None) -> None:
        self.repositories = repositories
        self.gamma = gamma or GammaClient()

    def collect(self) -> List[Event]:
        markets = self._fetch_markets()
        collected: List[Event] = []
        for market in markets:
            event = self._to_event(market)
            if event is None:
                continue
            self.repositories.events.upsert(event)
            collected.append(event)
        return collected

    def _fetch_markets(self) -> Iterable[Dict[str, Any]]:
        return self.gamma.fetch_markets(params={"category": settings.category_filter})

    def _to_event(self, market: Dict[str, Any]) -> Event | None:
        category = market.get("category") or market.get("category_name") or ""
        if category != settings.category_filter:
            return None
        return Event(
            event_id=str(market.get("event_id") or market.get("id")),
            market_id=str(market.get("market_id") or market.get("id")),
            title=str(market.get("question") or market.get("title") or ""),
            category=category,
            start_time=self._parse_datetime(market.get("start_date")),
            end_time=self._parse_datetime(market.get("end_date")),
            resolution=market.get("resolution"),
            status="resolved" if market.get("resolved") else "active",
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
