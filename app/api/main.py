from __future__ import annotations

from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
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


async def list_events(request: Request) -> JSONResponse:
    category = request.query_params.get("category", settings.category_filter)
    events = repositories.events.list_by_category(category)
    return JSONResponse([event.to_dict() for event in events])


async def list_crypto_events(request: Request) -> JSONResponse:
    days_param = request.query_params.get("days")
    days = int(days_param) if days_param and days_param.isdigit() else None
    events = collector.collect(category=settings.crypto_category, days=days)
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
      <h2>1) Select event & period</h2>
      <div class="grid">
        <div>
          <label class="muted" for="event-select">Crypto event</label>
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
        <button id="load-events">Load crypto events</button>
        <button id="ingest-events" class="secondary">Fetch data</button>
      </div>
      <span id="ingest-status" class="note"></span>
    </div>

    <div class="card">
      <h2>2) Events</h2>
      <div class="grid">
        <div>
          <button id="refresh-events" class="secondary">Refresh list</button>
          <p class="note">Total: <span id="event-count">0</span></p>
        </div>
        <div>
          <p class="muted">Selected event</p>
          <div id="selected-event" class="status">None</div>
          <p class="note" id="selected-meta"></p>
        </div>
      </div>
      <div id="event-error" class="error"></div>
      <table id="events-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Event ID</th>
            <th>Token</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <div class="card">
      <h2>3) Price + analytics</h2>
      <div class="grid">
        <div>
          <button id="ingest-price">Ingest latest price</button>
          <p class="note" id="price-status"></p>
        </div>
        <div>
          <button id="refresh-analytics" class="secondary">Refresh analytics</button>
          <p class="note" id="analytics-status"></p>
        </div>
      </div>
      <div id="analytics-card" class="note">No analytics loaded.</div>
    </div>

    <script>
      const state = { events: [], selected: null };

      const elements = {
        ingestBtn: document.getElementById("ingest-events"),
        loadBtn: document.getElementById("load-events"),
        eventSelect: document.getElementById("event-select"),
        periodSelect: document.getElementById("period-select"),
        ingestStatus: document.getElementById("ingest-status"),
        refreshBtn: document.getElementById("refresh-events"),
        eventCount: document.getElementById("event-count"),
        eventsTable: document.querySelector("#events-table tbody"),
        selectedEvent: document.getElementById("selected-event"),
        selectedMeta: document.getElementById("selected-meta"),
        eventError: document.getElementById("event-error"),
        ingestPriceBtn: document.getElementById("ingest-price"),
        priceStatus: document.getElementById("price-status"),
        analyticsBtn: document.getElementById("refresh-analytics"),
        analyticsStatus: document.getElementById("analytics-status"),
        analyticsCard: document.getElementById("analytics-card"),
      };

      function setSelected(event) {
        state.selected = event;
        if (!event) {
          elements.selectedEvent.textContent = "None";
          elements.selectedMeta.textContent = "";
          return;
        }
        elements.selectedEvent.textContent = event.title || "Untitled";
        elements.selectedMeta.textContent = `ID: ${event.event_id} • Token: ${event.token_id}`;
      }

      function renderEvents() {
        elements.eventsTable.innerHTML = "";
        elements.eventCount.textContent = String(state.events.length);
        state.events.forEach((event) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${event.title || "-"}</td>
            <td><span class="pill">${event.status}</span></td>
            <td>${event.event_id}</td>
            <td>${event.token_id}</td>
          `;
          row.addEventListener("click", () => setSelected(event));
          elements.eventsTable.appendChild(row);
        });
      }

      async function fetchEvents() {
        elements.eventError.textContent = "";
        const response = await fetch("/events");
        if (!response.ok) {
          elements.eventError.textContent = "Failed to load events.";
          return;
        }
        state.events = await response.json();
        renderEvents();
      }

      async function ingestEvents() {
        if (!elements.eventSelect.value) {
          elements.ingestStatus.textContent = "Choose an event first.";
          return;
        }
        const days = elements.periodSelect.value;
        const eventId = elements.eventSelect.value;
        elements.ingestStatus.textContent = "Fetching...";
        const response = await fetch(`/ingest/events?category=crypto&days=${days}&event_id=${eventId}`, { method: "POST" });
        if (!response.ok) {
          elements.ingestStatus.textContent = "Failed.";
          return;
        }
        const events = await response.json();
        elements.ingestStatus.textContent = `Fetched ${events.length} events.`;
        state.events = events;
        renderEvents();
      }

      async function loadCryptoEvents() {
        const days = elements.periodSelect.value;
        elements.ingestStatus.textContent = "Loading options...";
        const response = await fetch(`/options/crypto-events?days=${days}`);
        if (!response.ok) {
          elements.ingestStatus.textContent = "Failed to load options.";
          return;
        }
        const options = await response.json();
        elements.eventSelect.innerHTML = "";
        options.forEach((event) => {
          const option = document.createElement("option");
          option.value = event.event_id;
          option.textContent = event.title || event.event_id;
          option.dataset.tokenId = event.token_id;
          elements.eventSelect.appendChild(option);
        });
        if (options.length > 0) {
          setSelected(options[0]);
        }
        elements.ingestStatus.textContent = `Loaded ${options.length} events.`;
      }

      async function ingestPrice() {
        if (!state.selected) {
          elements.priceStatus.textContent = "Select an event first.";
          return;
        }
        elements.priceStatus.textContent = "Fetching price...";
        const response = await fetch(`/ingest/price/${state.selected.event_id}`, { method: "POST" });
        if (!response.ok) {
          elements.priceStatus.textContent = "Failed.";
          return;
        }
        const payload = await response.json();
        elements.priceStatus.textContent = `Latest price: ${payload.price}`;
      }

      async function refreshAnalytics() {
        if (!state.selected) {
          elements.analyticsStatus.textContent = "Select an event first.";
          return;
        }
        elements.analyticsStatus.textContent = "Loading...";
        const response = await fetch(`/events/${state.selected.event_id}/analytics`);
        if (!response.ok) {
          elements.analyticsStatus.textContent = "Failed.";
          return;
        }
        const analytics = await response.json();
        elements.analyticsStatus.textContent = "Updated.";
        elements.analyticsCard.innerHTML = `
          <div>Min price: <strong>${analytics.min_price ?? "-"}</strong></div>
          <div>Max price: <strong>${analytics.max_price ?? "-"}</strong></div>
          <div>Last price: <strong>${analytics.last_price ?? "-"}</strong></div>
        `;
      }

      elements.ingestBtn.addEventListener("click", ingestEvents);
      elements.loadBtn.addEventListener("click", loadCryptoEvents);
      elements.refreshBtn.addEventListener("click", fetchEvents);
      elements.ingestPriceBtn.addEventListener("click", ingestPrice);
      elements.analyticsBtn.addEventListener("click", refreshAnalytics);
      elements.eventSelect.addEventListener("change", (event) => {
        const selectedId = event.target.value;
        const found = state.events.find((item) => item.event_id === selectedId);
        if (found) {
          setSelected(found);
        } else {
          setSelected({ event_id: selectedId, title: event.target.selectedOptions[0].textContent, token_id: event.target.selectedOptions[0].dataset.tokenId, status: "unknown" });
        }
      });

      loadCryptoEvents();
      fetchEvents();
    </script>
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
        Route("/events/{event_id}", get_event, methods=["GET"]),
        Route("/events/{event_id}/analytics", get_event_analytics, methods=["GET"]),
    ]
)
