from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    category_filter: str = "crypto/15M"
    crypto_category: str = "crypto"


settings = Settings()
