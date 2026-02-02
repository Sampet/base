from __future__ import annotations

from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.analytics.aggregator import AnalyticsAggregator
from app.clients.clob import ClobClient
from app.config import settings
from app.db import RepositoryBundle
from app.ingestion.collector import EventCollector
from app.models import Event, EventAnalytics, PricePoint


app = Starlette(debug=False)
repositories = RepositoryBundle()
collector = EventCollector(repositories)
aggregator = AnalyticsAggregator(repositories)
clob_client = ClobClient()


async def ingest_events(request: Request) -> JSONResponse:
    events = collector.collect()
    return JSONResponse([event.to_dict() for event in events])


async def ingest_price(request: Request) -> JSONResponse:
    event_id = request.path_params["event_id"]
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
    return JSONResponse(point.to_dict())


async def list_events(request: Request) -> JSONResponse:
    category = request.query_params.get("category", settings.category_filter)
    events = repositories.events.list_by_category(category)
    return JSONResponse([event.to_dict() for event in events])


async def get_event(request: Request) -> JSONResponse:
    event_id = request.path_params["event_id"]
    event = repositories.events.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(event.to_dict())


async def get_event_analytics(request: Request) -> JSONResponse:
    event_id = request.path_params["event_id"]
    analytics = repositories.analytics.get(event_id)
    if analytics is None:
        analytics = aggregator.update_event_analytics(event_id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(analytics.to_dict())


app.routes.extend(
    [
        Route("/ingest/events", ingest_events, methods=["POST"]),
        Route("/ingest/price/{event_id}", ingest_price, methods=["POST"]),
        Route("/events", list_events, methods=["GET"]),
        Route("/events/{event_id}", get_event, methods=["GET"]),
        Route("/events/{event_id}/analytics", get_event_analytics, methods=["GET"]),
    ]
)
