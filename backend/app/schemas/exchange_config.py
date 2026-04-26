from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

SUPPORTED_EXCHANGES = {
    "delta_india": "Delta Exchange India",
    "zerodha": "Zerodha Kite (India)",
    "deribit": "Deribit",
    "okx": "OKX",
}


class ExchangeConfigCreate(BaseModel):
    name: str = Field(..., description="Adapter key: delta_india | deribit | okx")
    display_name: str = ""
    api_key: str = ""
    api_secret: str = ""
    is_paper: bool = True
    extra: Dict[str, Any] = {}


class ExchangeConfig(ExchangeConfigCreate):
    id: str
    is_active: bool = False

    def api_key_hint(self) -> str:
        if not self.api_key or len(self.api_key) < 4:
            return "****"
        return "****" + self.api_key[-4:]


class ExchangeConfigResponse(BaseModel):
    id: str
    name: str
    display_name: str
    api_key_hint: str
    is_paper: bool
    is_active: bool
    supported: bool
    extra: Dict[str, Any]


class ExchangeListResponse(BaseModel):
    exchanges: List[ExchangeConfigResponse]
    active_id: Optional[str]
    count: int


class ExchangeUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    is_paper: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None
