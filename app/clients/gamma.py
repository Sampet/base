from typing import Any, Dict, Iterable, Optional

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
