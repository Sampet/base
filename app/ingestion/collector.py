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
        self._tag_cache: Dict[str, Optional[str]] = {}

    def collect(
        self,
        category: Optional[str] = None,
        days: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> List[Event]:
        category_filter = category or settings.category_filter
        markets = self._fetch_markets(category_filter)
        collected: List[Event] = []
        cutoff = self._cutoff_datetime(days)
        for market in markets:
            event = self._to_event(market, category_filter)
            if event is None:
                continue
            if event_id and event.event_id != event_id:
                continue
            if cutoff and not self._is_recent(event, cutoff):
                continue
            self.repositories.events.upsert(event)
            collected.append(event)
        return collected

    def _fetch_markets(self, category_filter: str) -> Iterable[Dict[str, Any]]:
        if category_filter == settings.crypto_category:
            tag_id = self._get_tag_id(settings.crypto_category)
            if tag_id is not None:
                events = self.gamma.fetch_events(
                    params={"tag_id": tag_id, "active": "true", "closed": "false"}
                )
                if events:
                    return events
            return self.gamma.fetch_markets(params={"category": category_filter})
        return self.gamma.fetch_markets(params={"category": category_filter})

    def _to_event(self, market: Dict[str, Any], category_filter: str) -> Optional[Event]:
        category = market.get("category") or market.get("category_name") or ""
        if category_filter != settings.crypto_category and not self._matches_category(category, category_filter):
            return None
        token_id = market.get("token_id") or market.get("asset_id")
        if not token_id:
            token_ids = market.get("clobTokenIds") or market.get("clob_token_ids")
            if isinstance(token_ids, list) and token_ids:
                token_id = token_ids[0]
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

    @staticmethod
    def _normalize_category(value: str) -> str:
        return value.strip().lower().replace(" ", "")

    def _matches_category(self, category: str, category_filter: str) -> bool:
        normalized = self._normalize_category(category)
        target = self._normalize_category(category_filter)
        return normalized == target or target in normalized

    def _get_tag_id(self, tag_name: str) -> Optional[str]:
        normalized = self._normalize_category(tag_name)
        if normalized in self._tag_cache:
            return self._tag_cache[normalized]
        tags = self.gamma.fetch_tags()
        tag_id: Optional[str] = None
        for tag in tags:
            label = self._normalize_category(str(tag.get("label", "")))
            slug = self._normalize_category(str(tag.get("slug", "")))
            if label == normalized or slug == normalized:
                tag_id = str(tag.get("id"))
                break
        self._tag_cache[normalized] = tag_id
        return self._tag_cache[normalized]
