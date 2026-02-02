from __future__ import annotations

from datetime import datetime, timezone

from app.db import RepositoryBundle
from app.models import EventAnalytics


class AnalyticsAggregator:
    def __init__(self, repositories: RepositoryBundle) -> None:
        self.repositories = repositories

    def update_event_analytics(self, event_id: str) -> EventAnalytics | None:
        event = self.repositories.events.get(event_id)
        if event is None:
            return None
        end_time = event.end_time if event.status == "resolved" else datetime.now(tz=timezone.utc)
        prices = list(
            self.repositories.list_prices_in_window(
                market_id=event.market_id,
                start=event.start_time,
                end=end_time,
            )
        )
        if not prices:
            analytics = EventAnalytics(event_id=event.event_id)
            self.repositories.analytics.upsert(analytics)
            return analytics
        min_point = min(prices, key=lambda point: point.price)
        max_point = max(prices, key=lambda point: point.price)
        last_point = max(prices, key=lambda point: point.timestamp)
        analytics = EventAnalytics(
            event_id=event.event_id,
            min_price=min_point.price,
            min_price_time=min_point.timestamp,
            max_price=max_point.price,
            max_price_time=max_point.timestamp,
            last_price=last_point.price,
            last_price_time=last_point.timestamp,
        )
        self.repositories.analytics.upsert(analytics)
        return analytics
