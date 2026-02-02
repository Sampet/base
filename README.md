# Polymarket Crypto/15M Analytics

## Goal
Build a service that collects all current and resolved events from the **crypto/15M** section, stores their lifecycle metadata, and computes analytics per event:
- start time
- end time
- final resolution (if resolved)
- min/max probability (price) during the event window

## Architecture (High-level)
1. **Market discovery (Gamma API)**
   - Periodically fetch markets.
   - Filter by category/section: `crypto/15M`.
   - Persist events + market metadata.
2. **Price streaming (CLOB WebSocket/RTDS)**
   - Subscribe to tokens for discovered markets.
   - Persist price time series.
3. **Analytics processor**
   - Compute min/max price per event over `[start_time, end_time || now]`.
   - Store aggregated analytics.
4. **API service**
   - Expose endpoints to query events and analytics.

## Data model (MVP)
- `events`: core lifecycle info (start/end/resolution/status)
- `price_history`: time series price points by token/market
- `event_analytics`: precomputed min/max/last price

## Implementation plan (detailed)
1. **Scaffold project**
   - FastAPI app with typed models.
   - Config layer for API base URLs + DB URLs.
2. **Gamma client**
   - Fetch markets via Gamma API.
   - Normalize fields into `Event` records.
3. **CLOB client**
   - Fetch current price for token.
   - (Later) WebSocket/RTDS streaming.
4. **Persistence layer**
   - Abstract repository interfaces (event repo, price repo, analytics repo).
   - Start with in-memory implementation; swap for Postgres.
5. **Collector**
   - Scheduled job: fetch markets, upsert events, track tokens.
6. **Price ingestion**
   - Poll (temporary) + store price points; later upgrade to streaming.
7. **Analytics**
   - Compute min/max over event window; update aggregates.
8. **API endpoints**
   - `/events?category=crypto/15M`
   - `/events/{event_id}`
   - `/events/{event_id}/analytics`

## Running (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload
```
