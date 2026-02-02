from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.clients.gamma import GammaClient
from app.config import settings
from app.db import RepositoryBundle
from app.models import Event


class EventCollector:
    def __init__(self, repositories: RepositoryBundle, gamma: Optional[GammaClient] = None) -> None:
        self.repositories = repositories
        self.gamma = gamma or GammaClient()

    def collect(
        self,
        category: Optional[str] = None,
        days: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> List[Event]:
        markets = self._fetch_markets(category)
        collected: List[Event] = []
        cutoff = self._cutoff_datetime(days)
        for market in markets:
            event = self._to_event(market)
            if event is None:
                continue
            if event_id and event.event_id != event_id:
                continue
            if cutoff and not self._is_recent(event, cutoff):
                continue
            self.repositories.events.upsert(event)
            collected.append(event)
        return collected

    def _fetch_markets(self, category: Optional[str]) -> Iterable[Dict[str, Any]]:
        category_filter = category or settings.category_filter
        return self.gamma.fetch_markets(params={"category": category_filter})

    def _to_event(self, market: Dict[str, Any]) -> Optional[Event]:
        category = market.get("category") or market.get("category_name") or ""
        if category != settings.category_filter:
            return None
        token_id = market.get("token_id") or market.get("asset_id")
        if not token_id:
            return None
        return Event(
            event_id=str(market.get("event_id") or market.get("id")),
            market_id=str(market.get("market_id") or market.get("id")),
            token_id=str(token_id),
            title=str(market.get("question") or market.get("title") or ""),
            category=category,
            start_time=self._parse_datetime(market.get("start_date")),
            end_time=self._parse_datetime(market.get("end_date")),
            resolution=market.get("resolution"),
            status="resolved" if market.get("resolved") else "active",
        )

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _cutoff_datetime(days: Optional[int]) -> Optional[datetime]:
        if not days:
            return None
        return datetime.now(tz=timezone.utc) - timedelta(days=days)

    @staticmethod
    def _is_recent(event: Event, cutoff: datetime) -> bool:
        if event.start_time and event.start_time >= cutoff:
            return True
        if event.end_time and event.end_time >= cutoff:
            return True
        return False
