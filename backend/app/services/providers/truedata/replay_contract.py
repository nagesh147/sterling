"""Strict provenance and causal checks for Adaptive Edge TrueData replay.

This boundary is intentionally narrower than the general backtest provider
fallbacks: Adaptive Edge research replay must never accept synthetic data under
a TrueData label.
"""
from __future__ import annotations

from app.engines.adaptive_edge.replay import CanonicalEventSequence

TRUE_DATA_SOURCE = "truedata"
TRUE_DATA_VERSION = "2.6"


def require_truedata_sequence(sequence: CanonicalEventSequence, label: str) -> None:
    """Reject empty, synthetic, mixed-provider, or wrong-version sequences."""
    if not sequence.events:
        raise ValueError(f"{label} sequence is empty")

    bad = [
        event
        for event in sequence.events
        if event.source != TRUE_DATA_SOURCE or event.source_version != TRUE_DATA_VERSION
    ]
    if bad:
        sample = bad[0]
        raise ValueError(
            f"{label} contains non-TrueData provenance: "
            f"source={sample.source!r}, version={sample.source_version!r}, "
            f"record_id={sample.record_id}"
        )


def require_causal_order(sequence: CanonicalEventSequence, label: str) -> None:
    """Require causal availability and deterministic event ordering."""
    previous = None
    for event in sequence.events:
        if event.available_at < event.event_time:
            raise ValueError(
                f"{label} violates causal availability at {event.record_id}"
            )
        if previous is not None and (event.event_time, event.record_id) < (
            previous.event_time,
            previous.record_id,
        ):
            raise ValueError(f"{label} is not deterministically ordered")
        previous = event
