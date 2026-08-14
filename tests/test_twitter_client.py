"""twitter_client.py — RSSHub user-timeline köprüsü testleri (urllib mock).

keyword (arama) route'u X tarafında bozuldu (404→503); veri artık self-hosted
RSSHub /twitter/user/<handle> RSS'ten çekilir. Sabit finans/borsa hesaplarının
timeline'ları birleşir, gelen tweet'ler İZLENEN SEMBOLLERE göre süzülür.
RSSHUB_URL config'ten okunur (boşsa localhost:1200). Sembol çıkarma+filtre,
hesap başına ayrı istek, birleşik dedup+sort ve 429 backoff test edilir.
_parse_item sözleşmesi korunduğu için RSS helper aynı kalır.
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
    """Sabit RSSHub tabanı ve tek hesaplı liste varsay (test izolasyonu)."""
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "http://rsshub.test")
    monkeypatch.setattr(tc, "_DEFAULT_ACCOUNTS", ["acct1"])
    monkeypatch.setattr(tc.config, "TWITTER_ACCOUNTS", "", raising=False)


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


# ── sembol filtresi (izlenen sembolü içermeyen tweet elenir) ─────────────────
def test_symbol_filter_drops_unrelated():
    """İzlenen sembolü İÇERMEYEN tweet'ler süzülür (timeline karışık gelir)."""
    body = _rss([
        ("1", "THYAO ucdu", "ali", "Wed, 12 Aug 2026 09:00:00 GMT"),
        ("2", "hava durumu güzel", "ali", "Wed, 12 Aug 2026 09:01:00 GMT"),
    ])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, _users, err = _collect(tc.fetch_recent, "THYAO lang:tr -is:retweet")
    assert err is None
    assert [t["id"] for t in tweets] == ["1"]


def test_symbol_filter_word_boundary():
    """Kelime sınırı: THYAO, THYAOX içinde eşleşmemeli."""
    body = _rss([
        ("1", "THYAOX bir şey", "ali", "Wed, 12 Aug 2026 09:00:00 GMT"),
        ("2", "THYAO yükseldi", "ali", "Wed, 12 Aug 2026 09:01:00 GMT"),
    ])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, _users, err = _collect(tc.fetch_recent, "THYAO")
    assert [t["id"] for t in tweets] == ["2"]


def test_no_symbols_no_filter():
    """Sorguda sembol yoksa (operatör-only) süzme yapılmaz, tümü döner."""
    body = _rss([("1", "genel piyasa yorumu", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, _users, err = _collect(tc.fetch_recent, "lang:tr")
    assert err is None
    assert [t["id"] for t in tweets] == ["1"]


# ── author fallback: dc:creator yoksa handle link'ten, ad <author>'dan ────────
def test_author_from_link_and_author_tag():
    """user-timeline'da dc:creator olmayabilir: handle link'ten, ad <author>'dan."""
    body = (
        "<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
        "<item>"
        "<title>THYAO yorum</title>"
        "<link>https://x.com/borsainsan/status/999</link>"
        "<guid>https://x.com/borsainsan/status/999</guid>"
        "<author>Borsa İnsan</author>"
        "<pubDate>Wed, 12 Aug 2026 09:00:00 GMT</pubDate>"
        "</item></channel></rss>"
    ).encode("utf-8")
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        tweets, users, err = _collect(tc.fetch_recent, "THYAO")
    assert err is None
    assert tweets[0]["id"] == "999"
    assert tweets[0]["author_id"] == "borsainsan"        # handle link'ten
    assert users["borsainsan"]["name"] == "Borsa İnsan"  # ad <author>'dan


# ── fetch_ids ─────────────────────────────────────────────────────────────────
def test_fetch_ids_success():
    body = _rss([
        ("1", "THYAO a", "ali", "Wed, 12 Aug 2026 09:00:00 GMT"),
        ("2", "THYAO b", "veli", "Wed, 12 Aug 2026 09:01:00 GMT"),
    ])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        ids, err = _collect(tc.fetch_ids, "THYAO")
    assert err is None
    assert ids == {"1", "2"}


def test_fetch_ids_applies_symbol_filter():
    """fetch_ids de fetch_recent ile aynı sembol filtresini uygular."""
    body = _rss([
        ("1", "THYAO a", "ali", "Wed, 12 Aug 2026 09:00:00 GMT"),
        ("2", "alakasız tweet", "veli", "Wed, 12 Aug 2026 09:01:00 GMT"),
    ])
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        ids, err = _collect(tc.fetch_ids, "THYAO")
    assert err is None
    assert ids == {"1"}


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


def test_503_maps_to_token_hint():
    """RSSHub 503 = X token'ı geçersiz; kullanıcıya token'a işaret eden mesaj."""
    def side(req, timeout=None):
        raise _http_error(503)

    with patch("urllib.request.urlopen", side_effect=side):
        _tweets, _users, err = _collect(tc.fetch_recent, "THYAO")
    assert "token" in err.lower()


# ── çoklu hesap: hesap başına ayrı istek + birleşik dedup/sort ───────────────
def test_multi_account_separate_requests_and_merge(monkeypatch):
    monkeypatch.setattr(tc, "_DEFAULT_ACCOUNTS", ["acctA", "acctB"])
    calls = []

    def side(req, timeout=None):
        calls.append(req.full_url)
        if "acctA" in req.full_url:
            return _resp(_rss([("1", "THYAO", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")]))
        return _resp(_rss([("2", "THYAO daha yeni", "veli", "Wed, 12 Aug 2026 10:00:00 GMT")]))

    query = "THYAO lang:tr -is:retweet"
    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, query)

    assert err is None
    # her hesaba ayrı istek (user-timeline route)
    assert any("/twitter/user/acctA" in u for u in calls)
    assert any("/twitter/user/acctB" in u for u in calls)
    # birleşik + created_at azalan sıralı (10:00 önce)
    assert [t["id"] for t in tweets] == ["2", "1"]


def test_multi_account_dedup_by_id(monkeypatch):
    """Aynı tweet iki hesabın akışında da geçerse (RT vb.) tek kez görünür."""
    monkeypatch.setattr(tc, "_DEFAULT_ACCOUNTS", ["acctA", "acctB"])

    def side(req, timeout=None):
        return _resp(_rss([("7", "THYAO ve AKBNK", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")]))

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, "(THYAO OR AKBNK) lang:tr")
    assert err is None
    assert [t["id"] for t in tweets] == ["7"]


def test_partial_success_no_error(monkeypatch):
    """Bir hesap düşse de en az biri başarılıysa hata gösterilmez."""
    monkeypatch.setattr(tc, "_DEFAULT_ACCOUNTS", ["acctA", "acctB"])

    def side(req, timeout=None):
        if "acctA" in req.full_url:
            raise _http_error(500)
        return _resp(_rss([("2", "THYAO", "veli", "Wed, 12 Aug 2026 10:00:00 GMT")]))

    with patch("urllib.request.urlopen", side_effect=side):
        tweets, _users, err = _collect(tc.fetch_recent, "THYAO lang:tr")
    assert err is None
    assert [t["id"] for t in tweets] == ["2"]


# ── config.TWITTER_ACCOUNTS override ─────────────────────────────────────────
def test_accounts_from_config(monkeypatch):
    monkeypatch.setattr(tc.config, "TWITTER_ACCOUNTS", " @foo, bar ,, @baz ")
    assert tc._accounts() == ["foo", "bar", "baz"]


def test_accounts_default_when_empty(monkeypatch):
    monkeypatch.setattr(tc.config, "TWITTER_ACCOUNTS", "")
    monkeypatch.setattr(tc, "_DEFAULT_ACCOUNTS", ["x", "y"])
    assert tc._accounts() == ["x", "y"]


def test_user_route_in_url_and_no_retweets():
    """URL'de user-timeline route ve showRetweets=0 kullanılmalı."""
    captured = []

    def side(req, timeout=None):
        captured.append(req.full_url)
        return _resp(_rss([]))

    with patch("urllib.request.urlopen", side_effect=side):
        _collect(tc.fetch_ids, "THYAO lang:tr -is:retweet")
    assert captured
    assert "/twitter/user/acct1" in captured[0]
    assert "showRetweets=0" in captured[0]
    assert "keyword" not in captured[0]


# ── sembol çıkarma (filtre için) ─────────────────────────────────────────────
def test_symbols_from_query_multi():
    assert tc._symbols_from_query("(THYAO OR AKBNK) lang:tr -is:retweet") == ["THYAO", "AKBNK"]


def test_symbols_from_query_single_upper():
    assert tc._symbols_from_query("thyao lang:tr") == ["THYAO"]


def test_symbols_from_query_operators_only_empty():
    assert tc._symbols_from_query("lang:tr") == []
    assert tc._symbols_from_query("") == []


def test_symbols_from_query_dedup():
    assert tc._symbols_from_query("(THYAO OR THYAO) lang:tr") == ["THYAO"]


# ── 429 rate-limit (aynı istekte retry) ──────────────────────────────────────
def test_429_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)
    body = _rss([("1", "THYAO x", "ali", "Wed, 12 Aug 2026 09:00:00 GMT")])
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


# ── RSSHub tabanı yapılandırması ─────────────────────────────────────────────
def test_base_from_config(monkeypatch):
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "http://x.test:1200/")
    assert tc._rsshub_base() == "http://x.test:1200"


def test_base_default_when_empty(monkeypatch):
    monkeypatch.setattr(tc.config, "RSSHUB_URL", "")
    assert tc._rsshub_base() == tc._DEFAULT_RSSHUB
