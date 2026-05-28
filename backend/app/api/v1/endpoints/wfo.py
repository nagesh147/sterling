import os
import json
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/wfo", tags=["wfo"])

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "engines", "scalping", "whitelist.json")
IMPACT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "engines", "scalping", "impact.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "optimizer_cron.log")

@router.get("/state")
async def get_wfo_state():
    whitelist = {}
    impact = {}
    
    if os.path.exists(WHITELIST_PATH):
        try:
            with open(WHITELIST_PATH, "r") as f:
                whitelist = json.load(f)
        except Exception:
            pass
            
    if os.path.exists(IMPACT_PATH):
        try:
            with open(IMPACT_PATH, "r") as f:
                impact = json.load(f)
        except Exception:
            pass
            
    return {
        "whitelist": whitelist,
        "impact": impact
    }

@router.get("/logs")
async def get_wfo_logs(lines: int = 100):
    if not os.path.exists(LOG_PATH):
        return {"logs": ["Log file not found."]}
        
    try:
        with open(LOG_PATH, "r") as f:
            # Simple tail implementation
            lines_list = f.readlines()
            return {"logs": lines_list[-lines:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}

@router.post("/run")
async def run_wfo():
    # Start the optimizer asynchronously
    import subprocess
    cron_script = os.path.join(os.path.dirname(__file__), "..", "..", "..", "optimizer_cron.py")
    subprocess.Popen(["python3", cron_script], stdout=open(LOG_PATH, "a"), stderr=subprocess.STDOUT)
    return {"status": "started", "message": "Walk-Forward Optimizer launched in background."}
