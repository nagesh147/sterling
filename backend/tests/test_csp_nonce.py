"""The CSP, and the page it used to break.

`default-src 'none'` is right for a JSON API and wrong for the one route that
returns a document: the Kite callback. That page carries an inline stylesheet and
an inline script, and the strict policy blocked both.

The visible half was cosmetic — the page rendered as user-agent defaults. The
half that mattered was invisible: the blocked script is what posts
`kite-connected` to the already-open Sterling tab and closes the page. Without
it the app never learned the session had arrived, so the login looked like it had
failed, so the operator copied the `request_token` out of the URL and pasted it
— a token the callback had already spent, so it could only ever be rejected.
One header produced "login doesn't work", "I have to paste a token every time",
and "the token is always invalid".

So the page is allowed by NONCE, not by `unsafe-inline`: its own two tags run and
an injected one still cannot.
"""
import re

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def _csp(response) -> str:
    return response.headers.get("content-security-policy", "")


def test_a_json_response_keeps_the_strict_policy(client):
    # Nothing here needs to run a script or a style, so nothing may.
    r = client.get("/health")
    assert "default-src 'none'" in _csp(r)
    assert "nonce-" not in _csp(r), "the API must not hand out script permission"


def test_the_callback_page_is_allowed_by_nonce(client):
    r = client.get("/api/v1/kite/callback",
                   params={"action": "login", "status": "success", "request_token": "BOGUS"})
    assert r.headers["content-type"].startswith("text/html")
    policy = _csp(r)
    assert "style-src 'nonce-" in policy
    assert "script-src 'nonce-" in policy
    # Not a blanket allowance: an injected inline tag still has no nonce.
    assert "unsafe-inline" not in policy


def test_the_page_carries_the_SAME_nonce_the_header_grants(client):
    # The whole point. A nonce in the header that the page does not carry blocks
    # the page just as completely as no nonce at all — and does it silently.
    r = client.get("/api/v1/kite/callback",
                   params={"action": "login", "status": "success", "request_token": "BOGUS"})
    granted = re.search(r"style-src 'nonce-([\w-]+)'", _csp(r))
    assert granted, "header grants a style nonce"

    style_tag = re.search(r'<style nonce="([\w-]+)"', r.text)
    assert style_tag, "the style tag carries a nonce"
    assert style_tag.group(1) == granted.group(1)

    script_granted = re.search(r"script-src 'nonce-([\w-]+)'", _csp(r))
    assert script_granted and script_granted.group(1) == granted.group(1)


def test_the_nonce_is_fresh_per_request(client):
    # A reused nonce is a nonce an attacker can predict for the next response.
    def nonce_of():
        r = client.get("/api/v1/kite/callback",
                       params={"action": "login", "status": "success", "request_token": "BOGUS"})
        m = re.search(r"style-src 'nonce-([\w-]+)'", _csp(r))
        assert m
        return m.group(1)

    assert nonce_of() != nonce_of()


def test_the_page_still_has_its_stylesheet_to_protect(client):
    # If the inline style ever moves to a file this test is the reminder that the
    # nonce plumbing exists for it, and can go with it.
    r = client.get("/api/v1/kite/callback",
                   params={"action": "login", "status": "success", "request_token": "BOGUS"})
    assert "--k-" in r.text, "the page styles itself from the app's tokens"
    assert r.text.count("<style") == 1


def test_framing_stays_forbidden(client):
    # The page hands off by postMessage from a popup, never by being embedded, so
    # loosening the CSP for its own tags must not loosen this.
    r = client.get("/api/v1/kite/callback",
                   params={"action": "login", "status": "success", "request_token": "BOGUS"})
    assert "frame-ancestors 'none'" in _csp(r)
    assert r.headers.get("x-frame-options") == "DENY"
