# Observability

Three additive, opt-in facilities. None changes default runtime behavior; the
existing plain-text logging and the UI WebSocket log feed are untouched.

## Structured JSON logging

`app/core/observability.py`:

```python
from app.core.observability import configure_json_logging
configure_json_logging()   # no-op unless settings.log_json is true
```

Enable with the env var `LOG_JSON=true` (maps to `settings.log_json`). When on,
the root logger emits one JSON object per line: `timestamp`, `level`, `logger`,
`message`, `correlation_id` (when bound), `exc` (on errors), plus any structured
`extra=` fields. Default (`log_json=false`) keeps the current human format.

## Correlation IDs

Every HTTP request is tagged (FastAPI middleware in `main.py`): an inbound
`X-Correlation-ID` is honored, otherwise a fresh id is minted; it is bound to a
`contextvar` for the request's logging and echoed back as the
`X-Correlation-ID` response header. To correlate a non-HTTP flow (e.g. a trade
loop):

```python
from app.core.observability import correlation_scope
with correlation_scope() as cid:
    ...   # all logs in here carry correlation_id=cid
```

## Metrics

`app/core/metrics.py` — a tiny, thread-safe, in-process registry (no external
exporter required):

```python
from app.core import metrics
metrics.incr("orders_submitted")
metrics.observe("latency_ms", 12.4)
with metrics.timer("scan_ms"):
    ...
metrics.snapshot()   # {"counters": {...}, "summaries": {name: {count,sum,min,max,avg}}}
```

`snapshot()` is what a future `/metrics` endpoint or Prometheus exporter would
read. Tracing hooks can be layered on the same correlation-id contextvar.

## Tests

`tests/test_observability.py` pins the JSON shape, correlation-id round-trip, and
metric aggregation.
