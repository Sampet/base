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
        response = requests.get(url, params={"limit": limit}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("tags", [])
        return []

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
