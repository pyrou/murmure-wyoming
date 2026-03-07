from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    host: str
    port: int
    murmure_url: str
    model_name: str
    languages: list[str]
    api_timeout: float
    log_level: str
    attribution_name: str = "Kieirra / Murmure"
    attribution_url: str = "https://github.com/Kieirra/murmure"
