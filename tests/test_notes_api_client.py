"""notes_api_client.py — network boundary testleri (urllib mock)."""

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notes_api_client as nac


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    """Tüm testlerde GIST_ID/GITHUB_TOKEN dolu varsay (NotConfigured atlanır)."""
    monkeypatch.setattr(nac, "GIST_ID", "fake_gist")
    monkeypatch.setattr(nac, "GITHUB_TOKEN", "fake_token")


def _fake_response(data: dict):
    """urllib.request.urlopen için sahte context manager."""
    body = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── fetch_notes ──────────────────────────────────────────────────────────────
def test_fetch_notes_calls_callback_with_notes():
    payload = {
        "files": {
            "notes.json": {
                "content": json.dumps({"notes": ["not1", "not2"]})
            }
        }
    }
    received = []
    done = threading.Event()

    def cb(notes):
        received.append(notes)
        done.set()

    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        nac.fetch_notes(cb)
        done.wait(timeout=3)

    assert received == [["not1", "not2"]]


def test_fetch_notes_returns_none_on_network_error():
    received = []
    done = threading.Event()

    def cb(notes):
        received.append(notes)
        done.set()

    with patch("urllib.request.urlopen", side_effect=Exception("ağ hatası")):
        nac.fetch_notes(cb)
        done.wait(timeout=3)

    assert received == [None]


def test_fetch_notes_returns_none_on_missing_key():
    payload = {"files": {}}   # notes.json yok
    received = []
    done = threading.Event()

    def cb(notes):
        received.append(notes)
        done.set()

    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        nac.fetch_notes(cb)
        done.wait(timeout=3)

    assert received == [None]


# ── NotConfigured — kurulum eksikken ───────────────────────────────────────────
def test_is_configured():
    # fixture GIST_ID/GITHUB_TOKEN dolu yaptı
    assert nac.is_configured() is True


def test_fetch_notes_unconfigured(monkeypatch):
    """GIST_ID boşsa fetch_notes callback('unconfigured') çağırır, ağ isteği yok."""
    monkeypatch.setattr(nac, "GIST_ID", "")
    received = []
    done = threading.Event()

    def cb(notes):
        received.append(notes)
        done.set()

    # urlopen çağrılmamalı; çağrılırsa test patlar
    with patch("urllib.request.urlopen", side_effect=AssertionError("ağ isteği olmamalı")):
        nac.fetch_notes(cb)
        done.wait(timeout=3)

    assert received == ["unconfigured"]
def test_save_notes_calls_callback_true_on_success():
    received = []
    done = threading.Event()

    def cb(ok):
        received.append(ok)
        done.set()

    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        nac.save_notes(["not1"], cb)
        done.wait(timeout=3)

    assert received == [True]


def test_save_notes_calls_callback_none_on_error():
    received = []
    done = threading.Event()

    def cb(ok):
        received.append(ok)
        done.set()

    with patch("urllib.request.urlopen", side_effect=Exception("hata")):
        nac.save_notes(["not1"], cb)
        done.wait(timeout=3)

    assert received == [None]


def test_save_notes_no_callback_does_not_raise():
    done = threading.Event()
    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    def fake_urlopen(req, timeout=None):
        done.set()
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        nac.save_notes(["not1"])   # callback=None — çökme olmamalı
        assert done.wait(timeout=3)   # worker isteği gönderdi (sabit sleep yerine)


def test_save_notes_sends_correct_payload():
    captured = []
    done = threading.Event()

    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        done.set()
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        nac.save_notes(["notA", "notB"])
        done.wait(timeout=3)

    assert len(captured) == 1
    body = json.loads(captured[0].data.decode("utf-8"))
    content = json.loads(body["files"]["notes.json"]["content"])
    assert content["notes"] == ["notA", "notB"]


def _wait_for_idle_save_worker(timeout=3.0):
    """Sarkan _save_worker thread'i bitene kadar bekle (testler-arası izolasyon).

    _pending/_save_thread modül-global; önceki testten canlı bir worker kalırsa
    bu testin urlopen sayımına karışır. Başlamadan önce temiz zemin garanti et.
    """
    t = getattr(nac, "_save_thread", None)
    if t is not None and t.is_alive():
        t.join(timeout)


# ── save_notes eş zamanlı yarışı: "latest wins" ───────────────────────────────
def test_save_notes_concurrent_latest_wins():
    """Hızlı ardışık çağrılarda EN SON payload eninde sonunda gönderilir.

    save_notes sözleşmesi (docstring): "En son payload'ı gönderir; uçuşta istek
    varsa beklemez, yenisiyle ezer." Bu EVENTUAL latest-wins'tir:
      * garanti EDİLEN — son gönderilen payload ['son'] olur; ['son'] mutlaka gider;
        her save_notes en fazla bir worker turu tetikler → toplam istek ≤ 3.
      * garanti EDİLMEYEN — ara payload ['ikinci']'nin HİÇ gönderilmemesi. Belirli
        bir interleaving'de worker _pending'i ['ikinci'] iken okuyup gönderebilir,
        sonra ['son']'u da gönderir; got_son yine set olur. Eski test bunu yasaklayıp
        ~%2 oranında flaky oluyordu (implementasyonun vermediği bir garanti).
    Bu yüzden yalnızca gerçek sözleşmeyi doğrularız: son=['son'], ['son'] gönderildi,
    istek sayısı ≤ 3, ara payload gönderilmiş OLABİLİR (assert etmiyoruz).
    """
    _wait_for_idle_save_worker()   # önceki testten sarkan worker kalmasın

    sent_payloads = []
    lock = threading.Lock()
    got_son = threading.Event()

    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    def slow_urlopen(req, timeout=None):
        time.sleep(0.05)   # simüle gecikme — ara çağrılar _pending'i eziyor
        body = json.loads(req.data.decode("utf-8"))
        content = json.loads(body["files"]["notes.json"]["content"])
        with lock:
            sent_payloads.append(content["notes"])
        if content["notes"] == ["son"]:
            got_son.set()
        return resp

    with patch("urllib.request.urlopen", side_effect=slow_urlopen):
        nac.save_notes(["ilk"])
        nac.save_notes(["ikinci"])
        nac.save_notes(["son"])
        assert got_son.wait(timeout=3)   # ['son'] kesin gönderildi
        # Worker döngüsü tamamen dursun ki sent_payloads sabitlensin (yarış yok).
        _wait_for_idle_save_worker()

    with lock:
        # EVENTUAL latest-wins: en son gönderilen payload ['son'] olmalı.
        assert sent_payloads[-1] == ["son"]
        # Her save_notes en fazla bir worker turu tetikler → 3 çağrı, en fazla 3 istek.
        assert len(sent_payloads) <= 3
        # NOT: ['ikinci']'nin gönderilmemesini assert ETMİYORUZ — implementasyon
        # bunu garanti etmez (eventual, immediate değil). Eski assert flaky'ydi.
