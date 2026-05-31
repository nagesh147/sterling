import sys
import json

filepath = "backend/app/api/v1/endpoints/derivatives.py"
with open(filepath, "r") as f:
    content = f.read()

new_patch_config = """@router.post("/config", response_model=_ConfigResponse)
async def patch_config(body: _ConfigPatchRequest, request: Request) -> _ConfigResponse:
    from app.services.db import set_config
    import json
    from dataclasses import asdict

    overrides = _profile_overrides(request.app)
    overrides[body.profile.strategy] = body.profile
    
    # Persist to DB
    try:
        dict_overrides = {k: asdict(v) for k, v in overrides.items()}
        set_config("derivatives_profiles", json.dumps(dict_overrides))
    except Exception as e:
        log.warning(f"Failed to persist derivatives_profiles: {e}")
        
    return _ConfigResponse(profiles=overrides)"""

import re
content = re.sub(
    r'@router\.post\("/config", response_model=_ConfigResponse\)\nasync def patch_config\(body: _ConfigPatchRequest, request: Request\) -> _ConfigResponse:\n    overrides = _profile_overrides\(request\.app\)\n    overrides\[body\.profile\.strategy\] = body\.profile\n    return _ConfigResponse\(profiles=overrides\)',
    new_patch_config,
    content,
    count=1
)

with open(filepath, "w") as f:
    f.write(content)
print("Patched derivatives.py")
