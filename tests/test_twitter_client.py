"""twitter_client.py — RSSHub keyword köprüsü testleri (urllib mock).

Nitter ekosistemi çöktü; veri self-hosted RSSHub /twitter/keyword/<terim>
RSS'ten çekilir. RSSHUB_URL config'ten okunur (boşsa localhost:1200). X-stili
sorgudan sembol çıkarma, sembol başına ayrı istek, birleşik dedup+sort ve 429
backoff test edilir. _parse_item sözleşmesi korunduğu için RSS helper aynı kalır.
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
def _base(monkeypatch):
    """Sabit RSSHub tabanı varsay."""
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "http://rsshub.test")


def _rss(items):
    """items: [(id, text, creator, pubDate)] → RSS gövdesi (bytes)."""
    parts = []
    for tid, text, creator, pub in items:
        parts.append(
            f"<item>"
            f"<title>{text}</title>"
            f"<link>https://twitter.com/{creator}/status/{tid}</link>"
            f"<guid>https://twitter.com/{creator}/status/{tid}</guid>"
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
    """Bazı yanıtlar XML öncesi boşluk ekler → yine de parse edilmeli."""
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


# ── kaynak yok (RSSHub kapalı) ────────────────────────────────────────────────
def test_rsshub_down_returns_error():
    def side(req, timeout=None):
        raise urllib.error.URLError("Connection refused")

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, users, err = _collect(tc.fetch_recent, "THYAO")
    assert tweets == [] and users == {}
    assert err == "RSSHub kapalı"


def test_http_error_returns_error():
    def side(req, timeout=None):
        raise _http_error(500)

    with patch("urllib.request.urlopen", side_effect=side):
        _tweets, _users, err = _collect(tc.fetch_recent, "THYAO")
    assert err == "hata 500"


# ── çoklu sembol: sembol başına ayrı istek + birleşik dedup/sort ─────────────
def test_multi_symbol_separate_requests_and_merge():
    calls = []

    def side(req, timeout=None):
        calls.append(req.full_url)
        if "THYAO" in req.full_url:
            return _resp(_rss([("1", "THYAO", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")]))
        return _resp(_rss([("2", "AKBNK", "veli", "Wed, 12 Aug 2026 10:00:00 GMT")]))

    query = "(THYAO OR AKBNK) lang:tr -is:retweet"
    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, query)

    assert err is None
    # her sembole ayrı istek
    assert any("/twitter/keyword/THYAO" in u for u in calls)
    assert any("/twitter/keyword/AKBNK" in u for u in calls)
    # birleşik + created_at azalan sıralı (AKBNK 10:00 önce)
    assert [t["id"] for t in tweets] == ["2", "1"]


def test_multi_symbol_dedup_by_id():
    """Aynı tweet iki sembolde de geçerse tek kez görünür."""
    def side(req, timeout=None):
        return _resp(_rss([("7", "THYAO ve AKBNK", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")]))

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, "(THYAO OR AKBNK) lang:tr")
    assert err is None
    assert [t["id"] for t in tweets] == ["7"]


def test_partial_success_no_error():
    """Bir sembol düşse de en az biri başarılıysa hata gösterilmez."""
    def side(req, timeout=None):
        if "THYAO" in req.full_url:
            raise _http_error(500)
        return _resp(_rss([("2", "AKBNK", "veli", "Wed, 12 Aug 2026 10:00:00 GMT")]))

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, "(THYAO OR AKBNK) lang:tr")
    assert err is None
    assert [t["id"] for t in tweets] == ["2"]


# ── 429 rate-limit (aynı istekte retry) ──────────────────────────────────────
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


# ── keyword çıkarma ──────────────────────────────────────────────────────────
def test_keyword_from_query_multi():
    assert tc._keyword_from_query("(THYAO OR AKBNK) lang:tr -is:retweet") == ["THYAO", "AKBNK"]


def test_keyword_from_query_single():
    assert tc._keyword_from_query("THYAO lang:tr -is:retweet") == ["THYAO"]


def test_keyword_from_query_operators_only_fallback():
    # sıyırma sonrası boş kalırsa sorgunun tamamı tek terim
    assert tc._keyword_from_query("lang:tr") == ["lang:tr"]
    assert tc._keyword_from_query("") == []


def test_keyword_from_query_dedup():
    assert tc._keyword_from_query("(THYAO OR THYAO) lang:tr") == ["THYAO"]


def test_keyword_used_in_url():
    """URL'de keyword route ve operatörsüz terim kullanılmalı."""
    captured = []

    def side(req, timeout=None):
        captured.append(req.full_url)
        return _resp(_rss([]))

    with patch("urllib.request.urlopen", side_effect=side):
        _collect(tc.fetch_ids, "THYAO lang:tr -is:retweet")
    assert captured
    assert "/twitter/keyword/THYAO" in captured[0]
    assert "lang" not in captured[0]
    assert "is%3Aretweet" not in captured[0] and "is:retweet" not in captured[0]


# ── RSSHub tabanı yapılandırması ─────────────────────────────────────────────
def test_base_from_config(monkeypatch):
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "http://x.test:1200/")
    assert tc._rsshub_base() == "http://x.test:1200"


def test_base_default_when_empty(monkeypatch):
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "")
    assert tc._rsshub_base() == tc._DEFAULT_RSSHUB
