from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    environment: str = "development"
    paper_trading: bool = True
    real_public_data: bool = True
    default_underlying: str = "BTC"
    deribit_base_url: str = "https://www.deribit.com/api/v2"
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    exchange_adapter: str = "deribit"  # "deribit" | "okx"

    max_contracts: int = 10
    max_position_pct: float = 0.05
    default_capital: float = 100_000.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
            return [s.strip().strip('"\'') for s in stripped.split(",") if s.strip()]
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
