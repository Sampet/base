from __future__ import annotations

from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from app.analytics.aggregator import AnalyticsAggregator
from app.clients.clob import ClobClient
from app.clients.gamma import GammaClient
from app.config import settings
from app.db import RepositoryBundle
from app.ingestion.collector import EventCollector
from app.models import Event, EventAnalytics, PricePoint


app = Starlette(debug=False)
repositories = RepositoryBundle()
collector = EventCollector(repositories)
aggregator = AnalyticsAggregator(repositories)
clob_client = ClobClient()
gamma_client = GammaClient()


async def ingest_events(request: Request) -> JSONResponse:
    category = request.query_params.get("category") or settings.crypto_category
    event_id = request.query_params.get("event_id")
    days_param = request.query_params.get("days")
    days = int(days_param) if days_param and days_param.isdigit() else None
    events = collector.collect(category=category, days=days, event_id=event_id)
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


async def sample_price(request: Request) -> JSONResponse:
    event_id = request.query_params.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event_id is required")
    market = gamma_client.fetch_market_by_id(event_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found for event_id")
    token_ids = market.get("clobTokenIds") or market.get("clob_token_ids") or []
    if not isinstance(token_ids, list) or not token_ids:
        raise HTTPException(status_code=404, detail="No clob token id available")
    token_id = str(token_ids[0])
    payload = clob_client.fetch_price(token_id)
    price = float(payload.get("price", 0))
    point = PricePoint(
        market_id=str(market.get("id")),
        token_id=token_id,
        timestamp=datetime.now(tz=timezone.utc),
        price=price,
    )
    repositories.prices.add(point)
    return JSONResponse(point.to_dict())


async def price_history(request: Request) -> JSONResponse:
    event_id = request.query_params.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event_id is required")
    points = repositories.prices.list_for_market(event_id)
    payload = [point.to_dict() for point in points]
    return JSONResponse(payload)


async def list_events(request: Request) -> JSONResponse:
    category = request.query_params.get("category", settings.category_filter)
    events = repositories.events.list_by_category(category)
    return JSONResponse([event.to_dict() for event in events])


async def list_crypto_events(request: Request) -> JSONResponse:
    days_param = request.query_params.get("days")
    days = int(days_param) if days_param and days_param.isdigit() else None
    tag_param = request.query_params.get("tag_id")
    tag_id = tag_param.strip() if tag_param else None
    events = collector.collect(category=settings.crypto_category, days=days, tag_id=tag_id)
    payload = [
        {
            "event_id": event.event_id,
            "title": event.title,
            "token_id": event.token_id,
            "status": event.status,
        }
        for event in events
    ]
    return JSONResponse(payload)


async def list_tags(request: Request) -> JSONResponse:
    tags = collector.list_tags()
    filtered = []
    for tag in tags:
        slug = tag.get("slug")
        if not slug or "crypto" not in slug.lower():
            continue
        filtered.append(
            {
                "id": tag.get("id"),
                "slug": slug,
            }
        )
    payload = sorted(filtered, key=lambda item: item["slug"])
    return JSONResponse(payload)


async def list_events_by_tag(request: Request) -> JSONResponse:
    tag_id = request.query_params.get("tag_id")
    if not tag_id:
        raise HTTPException(status_code=400, detail="tag_id is required")
    events = gamma_client.fetch_markets_by_tag(tag_id)
    payload = [
        {
            "id": event.get("id"),
            "title": event.get("question") or event.get("title"),
        }
        for event in events
        if event.get("id")
    ]
    return JSONResponse(payload)


async def get_event_history(request: Request) -> JSONResponse:
    tag_id = request.query_params.get("tag_id")
    event_id = request.query_params.get("event_id")
    days_param = request.query_params.get("days")
    if not tag_id or not event_id or not days_param:
        raise HTTPException(status_code=400, detail="tag_id, event_id, and days are required")
    days = int(days_param) if days_param.isdigit() else None
    if not days:
        raise HTTPException(status_code=400, detail="days must be numeric")
    market = gamma_client.fetch_market_by_id(event_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found for event_id")
    start_time = collector._parse_datetime(market.get("startDate") or market.get("start_date"))
    end_time = collector._parse_datetime(market.get("endDate") or market.get("end_date"))
    outcome_prices = market.get("outcomePrices") or market.get("outcome_prices") or []
    prices = []
    for price in outcome_prices:
        try:
            prices.append(float(price))
        except (TypeError, ValueError):
            continue
    status = "closed" if market.get("closed") else "active"
    if market.get("resolved"):
        status = "resolved"
    volume = market.get("volume") or market.get("volumeNum") or market.get("volume_num")
    result = [
        {
            "event_id": market.get("id"),
            "title": market.get("question") or market.get("title"),
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "status": status,
            "max_probability": max(prices) if prices else None,
            "min_probability": min(prices) if prices else None,
            "total_volume": volume,
        }
    ]
    return JSONResponse(result)


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


def _render_homepage() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Polymarket Crypto/15M Analytics</title>
    <style>
      :root {
        color-scheme: light;
        font-family: "Inter", "Segoe UI", sans-serif;
        background: #f6f8fa;
        color: #1f2328;
      }
      body { margin: 0; padding: 2rem; }
      h1 { margin-bottom: 0.25rem; }
      h2 { margin-top: 2rem; }
      .card { background: #ffffff; border: 1px solid #d0d7de; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
      .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
      button { background: #0969da; color: #fff; border: none; border-radius: 6px; padding: 0.5rem 0.9rem; cursor: pointer; }
      button.secondary { background: #6e7781; }
      button:disabled { background: #94a3b8; cursor: not-allowed; }
      table { width: 100%; border-collapse: collapse; }
      th, td { padding: 0.5rem; border-bottom: 1px solid #eaeef2; text-align: left; font-size: 0.95rem; }
      code { background: #f6f8fa; padding: 0.1rem 0.25rem; border-radius: 4px; }
      .status { font-weight: 600; }
      .note { color: #57606a; }
      .error { color: #b42318; }
      .muted { color: #6e7781; }
      .pill { background: #eef2ff; color: #4338ca; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; }
    </style>
  </head>
  <body>
    <h1>Polymarket Crypto/15M Analytics</h1>
    <p class="note">Use this dashboard to fetch events, select one, and compute analytics.</p>

    <div class="card">
      <h2>1) Select tag, event & period</h2>
      <div class="grid">
        <div>
          <label class="muted" for="tag-select">Tag</label>
          <select id="tag-select" style="width:100%; padding:0.4rem; border-radius:6px; border:1px solid #d0d7de;"></select>
        </div>
        <div>
          <label class="muted" for="event-select">Event</label>
          <select id="event-select" style="width:100%; padding:0.4rem; border-radius:6px; border:1px solid #d0d7de;"></select>
        </div>
        <div>
          <label class="muted" for="period-select">Period</label>
          <select id="period-select" style="width:100%; padding:0.4rem; border-radius:6px; border:1px solid #d0d7de;">
            <option value="1">1 day</option>
            <option value="7" selected>7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
          </select>
        </div>
      </div>
      <p class="note">Choose a crypto event and period, then fetch data.</p>
      <div class="grid">
        <button id="load-tags">Load tags</button>
        <button id="load-events">Load events</button>
        <button id="fetch-history" class="secondary">Fetch history</button>
      </div>
      <span id="ingest-status" class="note"></span>
    </div>

    <div class="card">
      <h2>2) Event history</h2>
      <div id="event-error" class="error"></div>
      <table id="events-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Start</th>
            <th>End</th>
            <th>Min prob</th>
            <th>Max prob</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <div class="card">
      <h2>3) Probability over time</h2>
      <div class="grid">
        <button id="start-tracking">Start tracking price</button>
        <button id="stop-tracking" class="secondary">Stop tracking</button>
      </div>
      <canvas id="price-chart" height="120"></canvas>
      <p class="note">The chart uses sampled prices collected while tracking is running.</p>
    </div>

    <script>
      const state = { events: [], selected: null };

      const elements = {
        fetchBtn: document.getElementById("fetch-history"),
        loadBtn: document.getElementById("load-events"),
        loadTagsBtn: document.getElementById("load-tags"),
        eventSelect: document.getElementById("event-select"),
        tagSelect: document.getElementById("tag-select"),
        periodSelect: document.getElementById("period-select"),
        ingestStatus: document.getElementById("ingest-status"),
        eventsTable: document.querySelector("#events-table tbody"),
        eventError: document.getElementById("event-error"),
        startTracking: document.getElementById("start-tracking"),
        stopTracking: document.getElementById("stop-tracking"),
        chartCanvas: document.getElementById("price-chart"),
      };

      let priceChart = null;
      let trackingInterval = null;

      function renderHistory(events) {
        elements.eventsTable.innerHTML = "";
        events.forEach((event) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${event.title || "-"}</td>
            <td><span class="pill">${event.status}</span></td>
            <td>${event.start_time || "-"}</td>
            <td>${event.end_time || "-"}</td>
            <td>${event.min_probability ?? "-"}</td>
            <td>${event.max_probability ?? "-"}</td>
            <td>${event.total_volume ?? "-"}</td>
          `;
          elements.eventsTable.appendChild(row);
        });
      }

      async function loadCryptoEvents() {
        const tagId = elements.tagSelect.value;
        elements.ingestStatus.textContent = "Loading options...";
        const response = await fetch(`/options/events?tag_id=${tagId}`);
        if (!response.ok) {
          elements.ingestStatus.textContent = "Failed to load options.";
          return;
        }
        const options = await response.json();
        elements.eventSelect.innerHTML = "";
        options.forEach((event) => {
          const option = document.createElement("option");
          option.value = event.id;
          option.textContent = event.title || event.id;
          elements.eventSelect.appendChild(option);
        });
        if (options.length === 0) {
          elements.ingestStatus.textContent = "No events found for this tag.";
          return;
        }
        elements.eventSelect.value = options[0].id;
        elements.ingestStatus.textContent = `Loaded ${options.length} events.`;
      }

      async function fetchHistory() {
        elements.eventError.textContent = "";
        const tagId = elements.tagSelect.value;
        const eventId = elements.eventSelect.value;
        const days = elements.periodSelect.value;
        if (!tagId || !eventId) {
          elements.eventError.textContent = "Select a tag and event first.";
          return;
        }
        const response = await fetch(`/events/history?tag_id=${tagId}&event_id=${eventId}&days=${days}`);
        if (!response.ok) {
          let detail = "Failed to load history.";
          try {
            const payload = await response.json();
            if (payload && payload.detail) {
              detail = payload.detail;
            }
          } catch (error) {
            // ignore parse errors
          }
          elements.eventError.textContent = detail;
          return;
        }
        const events = await response.json();
        renderHistory(events);
        await loadPriceHistory();
      }

      async function loadPriceHistory() {
        const eventId = elements.eventSelect.value;
        if (!eventId) {
          return;
        }
        const response = await fetch(`/events/price-history?event_id=${eventId}`);
        if (!response.ok) {
          return;
        }
        const points = await response.json();
        const labels = points.map((point) => point.timestamp);
        const data = points.map((point) => point.price);
        renderChart(labels, data);
      }

      async function samplePrice() {
        const eventId = elements.eventSelect.value;
        if (!eventId) {
          elements.eventError.textContent = "Select an event first.";
          return;
        }
        await fetch(`/events/price-sample?event_id=${eventId}`, { method: "POST" });
        await loadPriceHistory();
      }

      function renderChart(labels, data) {
        if (!window.Chart) {
          return;
        }
        if (priceChart) {
          priceChart.destroy();
        }
        const ctx = elements.chartCanvas.getContext("2d");
        priceChart = new Chart(ctx, {
          type: "line",
          data: {
            labels,
            datasets: [
              {
                label: "Probability",
                data,
                borderColor: "#0969da",
                backgroundColor: "rgba(9, 105, 218, 0.1)",
                tension: 0.2,
              },
            ],
          },
          options: {
            scales: {
              y: {
                min: 0,
                max: 1,
              },
            },
          },
        });
      }

      async function loadTags() {
        elements.ingestStatus.textContent = "Loading tags...";
        const response = await fetch("/options/tags");
        if (!response.ok) {
          elements.ingestStatus.textContent = "Failed to load tags.";
          return;
        }
        const tags = await response.json();
        elements.tagSelect.innerHTML = "";
        tags.forEach((tag) => {
          const option = document.createElement("option");
          option.value = tag.id;
          option.textContent = tag.slug || tag.id;
          elements.tagSelect.appendChild(option);
        });
        elements.ingestStatus.textContent = `Loaded ${tags.length} tags.`;
      }

      elements.fetchBtn.addEventListener("click", fetchHistory);
      elements.loadTagsBtn.addEventListener("click", loadTags);
      elements.loadBtn.addEventListener("click", loadCryptoEvents);
      elements.tagSelect.addEventListener("change", () => {
        loadCryptoEvents();
      });
      elements.startTracking.addEventListener("click", () => {
        if (trackingInterval) {
          return;
        }
        samplePrice();
        trackingInterval = setInterval(samplePrice, 30000);
      });
      elements.stopTracking.addEventListener("click", () => {
        if (trackingInterval) {
          clearInterval(trackingInterval);
          trackingInterval = null;
        }
      });

      loadTags();
    </script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  </body>
</html>
"""


async def homepage(request: Request) -> HTMLResponse:
    return HTMLResponse(_render_homepage())


app.routes.extend(
    [
        Route("/", homepage, methods=["GET"]),
        Route("/ingest/events", ingest_events, methods=["POST"]),
        Route("/ingest/price/{event_id}", ingest_price, methods=["POST"]),
        Route("/events", list_events, methods=["GET"]),
        Route("/options/crypto-events", list_crypto_events, methods=["GET"]),
        Route("/options/events", list_events_by_tag, methods=["GET"]),
        Route("/options/tags", list_tags, methods=["GET"]),
        Route("/events/history", get_event_history, methods=["GET"]),
        Route("/events/price-sample", sample_price, methods=["POST"]),
        Route("/events/price-history", price_history, methods=["GET"]),
        Route("/events/{event_id}", get_event, methods=["GET"]),
        Route("/events/{event_id}/analytics", get_event_analytics, methods=["GET"]),
    ]
)
