import json
import sys
sys.path.append("/home/nageshmadaram/Sterling/backend")
from app.services.db import get_config, set_config, init

init()
dp_str = get_config("derivatives_profiles")
if dp_str:
    parsed = json.loads(dp_str)
    for k, v in parsed.items():
        v["min_oi"] = 1.0
        v["min_volume_24h_x_contract"] = 1.0
    set_config("derivatives_profiles", json.dumps(parsed))
    print("Fixed!")
else:
    print("No derivatives_profiles in DB")
