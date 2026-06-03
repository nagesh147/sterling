from fastapi import APIRouter
from pydantic import BaseModel

from app.engines.sterling_v2.config import (
    V2_ENABLED_DEFAULT, V2_PAPER_ONLY, V2_AUTO_EXECUTE,
)

router = APIRouter(prefix="/sterling-v2", tags=["sterling_v2"])


class V2Config(BaseModel):
    enabled: bool = V2_ENABLED_DEFAULT
    paper_only: bool = V2_PAPER_ONLY
    auto_execute: bool = V2_AUTO_EXECUTE


_config = V2Config()


@router.get("/config", response_model=V2Config)
def get_config() -> V2Config:
    return _config


@router.get("/health")
def health() -> dict:
    return {"engine": "sterling_v2", "status": "skeleton"}
