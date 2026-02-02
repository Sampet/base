from typing import Any, Dict, Optional

import requests

from app.config import settings


class ClobClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.clob_base_url

    def fetch_price(self, token_id: str, side: str = "buy") -> Dict[str, Any]:
        url = f"{self.base_url}/price"
        response = requests.get(url, params={"token_id": token_id, "side": side}, timeout=30)
        response.raise_for_status()
        return response.json()
