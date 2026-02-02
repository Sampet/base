from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException

from app.analytics.aggregator import AnalyticsAggregator
from app.clients.clob import ClobClient
from app.config import settings
from app.db import RepositoryBundle
from app.ingestion.collector import EventCollector
from app.models import Event, EventAnalytics, PricePoint

app = FastAPI(title="Polymarket Crypto/15M Analytics")
repositories = RepositoryBundle()
collector = EventCollector(repositories)
aggregator = AnalyticsAggregator(repositories)
clob_client = ClobClient()


@app.post("/ingest/events", response_model=List[Event])
def ingest_events() -> List[Event]:
    return collector.collect()


@app.post("/ingest/price/{event_id}", response_model=PricePoint)
def ingest_price(event_id: str) -> PricePoint:
    event = repositories.events.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    token_id = event.token_id
    payload = clob_client.fetch_price(token_id)
    price = float(payload.get("price", 0))
    point = PricePoint(
        market_id=event.market_id,
        token_id=token_id,
        timestamp=datetime.now(tz=timezone.utc),
        price=price,
    )
    repositories.prices.add(point)
    return point


@app.get("/events", response_model=List[Event])
def list_events(category: str = settings.category_filter) -> List[Event]:
    return repositories.events.list_by_category(category)


@app.get("/events/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    event = repositories.events.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/events/{event_id}/analytics", response_model=EventAnalytics)
def get_event_analytics(event_id: str) -> EventAnalytics:
    analytics = repositories.analytics.get(event_id)
    if analytics is None:
        analytics = aggregator.update_event_analytics(event_id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return analytics
