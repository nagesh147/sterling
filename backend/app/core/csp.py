"""The per-request CSP nonce.

The API serves `default-src 'none'`, which is right for JSON and wrong for the
one route that returns a page: the Kite callback. That page is a self-contained
document with an inline stylesheet and an inline script, and the strict policy
blocked both — so it rendered as user-agent defaults and, worse, its handoff
script never ran, which is what tells the already-open Sterling tab that the
session arrived.

The page is allowed by NONCE rather than by `unsafe-inline`, so its own two tags
run and an injected one still cannot. That needs the value in two places: the
middleware, which mints it and writes the header, and the handler, which stamps
it on the tags it emits.

A ContextVar rather than a parameter, deliberately. Threading it would mean
touching every `_callback_page(...)` call — there are eight, several of them
error paths — and a nonce the page forgets to carry is not a broken build, it is
a page that silently loses its styling and its handoff. Exactly the failure this
exists to fix.
"""
from __future__ import annotations

from contextvars import ContextVar

_csp_nonce: ContextVar[str] = ContextVar("csp_nonce", default="")


def set_csp_nonce(value: str) -> object:
    """Bind the nonce for this request. Returns the reset token."""
    return _csp_nonce.set(value)


def reset_csp_nonce(token: object) -> None:
    _csp_nonce.reset(token)  # type: ignore[arg-type]


def csp_nonce() -> str:
    """This request's nonce, or "" outside a request (tests, scripts)."""
    return _csp_nonce.get()
