"""twitter_client.py — Nitter RSS köprüsü testleri (urllib mock).

X API v2 402 sonrası veri Nitter search RSS'ten çekilir. Bearer token yok;
çoklu instance fallback + 429 backoff + X-operatör sıyırma test edilir.
"""

import os
import sys
import threading
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import twitter_client as tc


@pytest.fixture(autouse=True)
def _instances(monkeypatch):
    """Tek sabit instance varsay (fallback döngüsü ayrı test edilir)."""
    monkeypatch.setattr(tc.config, "NITTER_INSTANCES", "https://nitter.test")


def _rss(items):
    """items: [(id, text, creator, pubDate)] → RSS gövdesi (bytes)."""
    parts = []
    for tid, text, creator, pub in items:
        parts.append(
            f"<item>"
            f"<title>{text}</title>"
            f"<link>https://nitter.test/{creator}/status/{tid}#m</link>"
            f"<guid>https://nitter.test/{creator}/status/{tid}#m</guid>"
            f"<dc:creator xmlns:dc='http://purl.org/dc/elements/1.1/'>@{creator}</dc:creator>"
            f"<pubDate>{pub}</pubDate>"
            f"</item>"
        )
    body = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<rss version='2.0'><channel>" + "".join(parts) + "</channel></rss>"
    )
    return body.encode("utf-8")


def _resp(body: bytes):
    r = MagicMock()
    r.read.return_value = body
    r.__enter__ = lambda s: s
    r.__exit__ = MagicMock(return_value=False)
    return r


def _http_error(code, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("url", code, "err", headers, BytesIO(b""))


def _collect(fn, query):
    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    fn(query, cb)
    done.wait(timeout=3)
    return got[0]


# ── fetch_recent ────────────────────────────────────────────────────────────
def test_fetch_recent_success():
    body = _rss([("1", "THYAO ucdu", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, users, err = _collect(tc.fetch_recent, "THYAO")

    assert err is None
    assert tweets[0]["id"] == "1"
    assert tweets[0]["text"] == "THYAO ucdu"
    assert tweets[0]["author_id"] == "ali"
    assert tweets[0]["created_at"].startswith("2026-08-12T09:00:00")
    assert users["ali"]["username"] == "ali"


def test_fetch_recent_html_unescape():
    body = _rss([("2", "AKBNK &amp; GARAN", "veli", "Wed, 12 Aug 2026 09:00:00 GMT")])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, _users, err = _collect(tc.fetch_recent, "AKBNK")
    assert err is None
    assert tweets[0]["text"] == "AKBNK & GARAN"


def test_fetch_recent_leading_whitespace():
    """Bazı instance'lar XML öncesi boşluk ekler → yine de parse edilmeli."""
    body = b"  \n  " + _rss([("3", "ISCTR", "can", "Wed, 12 Aug 2026 09:00:00 GMT")])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, _users, err = _collect(tc.fetch_recent, "ISCTR")
    assert err is None
    assert tweets[0]["id"] == "3"


# ── fetch_ids ─────────────────────────────────────────────────────────────────
def test_fetch_ids_success():
    body = _rss([
        ("1", "a", "ali", "Wed, 12 Aug 2026 09:00:00 GMT"),
        ("2", "b", "veli", "Wed, 12 Aug 2026 09:01:00 GMT"),
    ])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        ids, err = _collect(tc.fetch_ids, "THYAO")
    assert err is None
    assert ids == {"1", "2"}


# ── kaynak yok (tüm instance düşer) ─────────────────────────────────────────
def test_all_instances_down_returns_error(monkeypatch):
    monkeypatch.setattr(tc.config, "NITTER_INSTANCES", "https://a.test,https://b.test")

    def side(req, timeout=None):
        raise _http_error(500)

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, users, err = _collect(tc.fetch_recent, "THYAO")
    assert tweets == [] and users == {}
    assert err == "hata 500"


# ── çoklu instance fallback ──────────────────────────────────────────────────
def test_instance_fallback(monkeypatch):
    """İlk instance düşer, ikincisi başarılı → veri ikinciden gelir."""
    monkeypatch.setattr(tc.config, "NITTER_INSTANCES", "https://a.test,https://b.test")
    body = _rss([("9", "SASA", "ece", "Wed, 12 Aug 2026 09:00:00 GMT")])
    calls = []

    def side(req, timeout=None):
        calls.append(req.full_url)
        if "a.test" in req.full_url:
            raise _http_error(503)
        return _resp(body)

    with patch("urllib.request.urlopen", side_effect=side):
        ids, err = _collect(tc.fetch_ids, "SASA")
    assert err is None
    assert ids == {"9"}
    assert any("a.test" in u for u in calls) and any("b.test" in u for u in calls)


# ── 429 rate-limit (aynı instance içinde retry) ──────────────────────────────
def test_429_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)
    body = _rss([("1", "x", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")])
    calls = [0]

    def side(req, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            raise _http_error(429, retry_after=1)
        return _resp(body)

    with patch("urllib.request.urlopen", side_effect=side):
        ids, err = _collect(tc.fetch_ids, "THYAO")
    assert err is None
    assert ids == {"1"}
    assert calls[0] == 2   # bir retry


def test_retry_after_capped(monkeypatch):
    """Retry-After çok büyükse _MAX_BACKOFF ile sınırlanır."""
    waited = []
    monkeypatch.setattr(tc.time, "sleep", lambda s: waited.append(s))
    body = _rss([])
    calls = [0]

    def side(req, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            raise _http_error(429, retry_after=99999)
        return _resp(body)

    with patch("urllib.request.urlopen", side_effect=side):
        _collect(tc.fetch_ids, "THYAO")
    assert waited and waited[0] <= tc._MAX_BACKOFF


# ── X-özel operatör sıyırma ──────────────────────────────────────────────────
def test_clean_query_strips_x_operators():
    assert tc._clean_query("(THYAO OR AKBNK) lang:tr -is:retweet") == "(THYAO OR AKBNK)"
    assert tc._clean_query("THYAO lang:tr") == "THYAO"
    # sıyırma sonrası boş kalırsa orijinal korunur
    assert tc._clean_query("lang:tr") == "lang:tr"


def test_clean_query_passed_to_url():
    """URL'de temizlenmiş sorgu (operatörsüz) kullanılmalı."""
    body = _rss([])
    captured = []

    def side(req, timeout=None):
        captured.append(req.full_url)
        return _resp(body)

    with patch("urllib.request.urlopen", side_effect=side):
        _collect(tc.fetch_ids, "(THYAO OR AKBNK) lang:tr -is:retweet")
    assert captured
    assert "lang" not in captured[0]
    assert "is%3Aretweet" not in captured[0] and "is:retweet" not in captured[0]


# ── instance yapılandırması ──────────────────────────────────────────────────
def test_instances_from_config(monkeypatch):
    monkeypatch.setattr(tc.config, "NITTER_INSTANCES", "https://x.test/, https://y.test")
    assert tc._instances() == ["https://x.test", "https://y.test"]


def test_instances_default_when_empty(monkeypatch):
    monkeypatch.setattr(tc.config, "NITTER_INSTANCES", "")
    assert tc._instances() == tc._DEFAULT_INSTANCES
