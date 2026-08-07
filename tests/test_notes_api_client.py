"""notes_api_client.py — network boundary testleri (urllib mock)."""

import json
import os
import sys
import threading
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notes_api_client as nac


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


# ── save_notes ───────────────────────────────────────────────────────────────
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
    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        nac.save_notes(["not1"])   # callback=None
        import time; time.sleep(0.2)   # thread'in bitmesini bekle


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


# ── save_notes eş zamanlı yarışı: "latest wins" ───────────────────────────────
def test_save_notes_concurrent_latest_wins():
    """Hızlı ardışık çağrılarda son payload gönderilmeli."""
    import time
    sent_payloads = []
    call_count = [0]
    done = threading.Event()

    resp = MagicMock()
    resp.read.return_value = b""
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    def slow_urlopen(req, timeout=None):
        call_count[0] += 1
        time.sleep(0.05)   # simüle gecikme
        body = json.loads(req.data.decode("utf-8"))
        content = json.loads(body["files"]["notes.json"]["content"])
        sent_payloads.append(content["notes"])
        if call_count[0] >= 1:
            done.set()
        return resp

    with patch("urllib.request.urlopen", side_effect=slow_urlopen):
        nac.save_notes(["ilk"])
        nac.save_notes(["ikinci"])
        nac.save_notes(["son"])
        done.wait(timeout=3)
        time.sleep(0.2)   # worker'ın ikinci turunu da bekle

    # Son payload gönderilmiş olmalı
    assert sent_payloads[-1] == ["son"]
