from typing import Any, Dict, Iterable, List, Optional

import requests

from app.config import settings


class GammaClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.gamma_base_url

    def fetch_markets(self, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
        url = f"{self.base_url}/markets"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("markets", [])
        return []

    def fetch_tags(self, limit: int = 100) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/tags"
        all_tags: List[Dict[str, Any]] = []
        offset = 0
        while True:
            response = requests.get(
                url,
                params={"limit": limit, "offset": offset},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                batch = payload
            elif isinstance(payload, dict):
                batch = payload.get("tags", [])
            else:
                batch = []
            if not batch:
                break
            all_tags.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return all_tags

    def fetch_events(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/events"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("events", [])
        return []

    def fetch_markets_by_tag(self, tag_id: str) -> List[Dict[str, Any]]:
        return list(self.fetch_markets(params={"tag_id": tag_id}))

    def fetch_market_by_id(self, market_id: str) -> Optional[Dict[str, Any]]:
        markets = self.fetch_markets(params={"id": market_id})
        if markets:
            return markets[0]
        markets = self.fetch_markets(params={"ids": market_id})
        for market in markets:
            if str(market.get("id")) == str(market_id):
                return market
        return None
