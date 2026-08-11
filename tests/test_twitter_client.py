"""twitter_client.py — ağ sınırı + 429 rate-limit testleri (urllib mock)."""

import json
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
def _token(monkeypatch):
    """config.TWITTER_BEARER_TOKEN dolu varsay."""
    monkeypatch.setattr(tc.config, "TWITTER_BEARER_TOKEN", "fake_bearer")


def _resp(data: dict):
    body = json.dumps(data).encode("utf-8")
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


# ── fetch_recent ───────────────────────────────────────────────────────────────
def test_fetch_recent_success():
    payload = {
        "data": [{"id": "1", "text": "THYAO ucdu", "author_id": "u1"}],
        "includes": {"users": [{"id": "u1", "username": "ali", "name": "Ali"}]},
    }
    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    with patch("urllib.request.urlopen", return_value=_resp(payload)):
        tc.fetch_recent("THYAO", cb)
        done.wait(timeout=3)

    tweets, users, err = got[0]
    assert err is None
    assert tweets[0]["id"] == "1"
    assert users["u1"]["username"] == "ali"


def test_fetch_recent_no_token(monkeypatch):
    monkeypatch.setattr(tc.config, "TWITTER_BEARER_TOKEN", "")
    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    with patch("urllib.request.urlopen", side_effect=AssertionError("ağ olmamalı")):
        tc.fetch_recent("THYAO", cb)
        done.wait(timeout=3)

    tweets, users, err = got[0]
    assert tweets == [] and users == {} and err == "token yok"


# ── fetch_ids ──────────────────────────────────────────────────────────────────
def test_fetch_ids_success():
    payload = {"data": [{"id": "1"}, {"id": "2"}]}
    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    with patch("urllib.request.urlopen", return_value=_resp(payload)):
        tc.fetch_ids("THYAO", cb)
        done.wait(timeout=3)

    ids, err = got[0]
    assert err is None
    assert ids == {"1", "2"}


# ── 429 rate-limit ─────────────────────────────────────────────────────────────
def test_429_retries_then_succeeds(monkeypatch):
    """İlk çağrı 429, ikinci başarılı → sonuç başarılı olmalı, bekleme kısa."""
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)   # testte bekleme yok
    calls = [0]
    payload = {"data": [{"id": "1"}]}

    def side(req, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            raise _http_error(429, retry_after=1)
        return _resp(payload)

    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    with patch("urllib.request.urlopen", side_effect=side):
        tc.fetch_ids("THYAO", cb)
        done.wait(timeout=3)

    ids, err = got[0]
    assert err is None
    assert ids == {"1"}
    assert calls[0] == 2   # bir retry


def test_429_exhausts_retries(monkeypatch):
    """Sürekli 429 → rate-limit hatası döner, sonsuz denemez."""
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)
    calls = [0]

    def side(req, timeout=None):
        calls[0] += 1
        raise _http_error(429, retry_after=1)

    got = []
    done = threading.Event()

    def cb(result):
        got.append(result)
        done.set()

    with patch("urllib.request.urlopen", side_effect=side):
        tc.fetch_ids("THYAO", cb)
        done.wait(timeout=3)

    ids, err = got[0]
    assert err == "rate-limit"
    # _MAX_RETRIES + 1 deneme (fazlası değil)
    assert calls[0] == tc._MAX_RETRIES + 1


def test_retry_after_capped(monkeypatch):
    """Retry-After çok büyükse _MAX_BACKOFF ile sınırlanır (UI kilitlenmez)."""
    waited = []
    monkeypatch.setattr(tc.time, "sleep", lambda s: waited.append(s))
    calls = [0]
    payload = {"data": []}

    def side(req, timeout=None):
        calls[0] += 1
        if calls[0] == 1:
            raise _http_error(429, retry_after=99999)
        return _resp(payload)

    done = threading.Event()
    with patch("urllib.request.urlopen", side_effect=side):
        tc.fetch_ids("THYAO", lambda r: done.set())
        done.wait(timeout=3)

    assert waited and waited[0] <= tc._MAX_BACKOFF


def test_non_429_http_error(monkeypatch):
    """429 dışı HTTP hatası → tek denemede 'hata <code>' döner."""
    calls = [0]

    def side(req, timeout=None):
        calls[0] += 1
        raise _http_error(500)

    got = []
    done = threading.Event()
    with patch("urllib.request.urlopen", side_effect=side):
        tc.fetch_ids("THYAO", lambda r: (got.append(r), done.set()))
        done.wait(timeout=3)

    ids, err = got[0]
    assert err == "hata 500"
    assert calls[0] == 1   # retry yok
