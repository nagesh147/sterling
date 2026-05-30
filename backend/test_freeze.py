from app.engines.derivatives.freeze_token import get_store, FreezeEntry
from app.engines.derivatives.schemas import DerivativesDecision, DecisionStatus

store = get_store()
decision = DerivativesDecision(status=DecisionStatus.OK)
token, ttl = store.freeze(decision)
print(f"Token: {token}")

import time
time.sleep(1)

decision_out = store.consume(token)
print(f"Decision: {decision_out is not None}")
