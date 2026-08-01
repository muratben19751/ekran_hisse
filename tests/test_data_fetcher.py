"""data_fetcher.py — saf yardımcı fonksiyon testleri."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

df = pytest.importorskip("data_fetcher")   # websocket bağımlılığı yoksa atla


# ── _parse_packets ───────────────────────────────────────────────────────────
def test_parse_packets_single():
    assert df._parse_packets("~m~5~m~hello") == ["hello"]


def test_parse_packets_multiple():
    data = "~m~5~m~hello~m~5~m~world"
    assert df._parse_packets(data) == ["hello", "world"]


def test_parse_packets_empty():
    assert df._parse_packets("") == []


# ── _wrap ────────────────────────────────────────────────────────────────────
def test_wrap_format():
    msg = {"m": "x"}
    wrapped = df._wrap(msg)
    body = json.dumps(msg)
    assert wrapped == f"~m~{len(body)}~m~{body}"


def test_wrap_length_matches():
    wrapped = df._wrap({"m": "quote_add_symbols", "p": [1, 2]})
    # ~m~<len>~m~<body> → len alanı gerçek gövde uzunluğuna eşit olmalı
    prefix, body = wrapped.split("~m~")[1], wrapped.split("~m~", 2)[2]
    assert int(prefix) == len(body)


# ── _tv_symbol ───────────────────────────────────────────────────────────────
def test_tv_symbol():
    assert df._tv_symbol("thyao") == "BIST:THYAO"
    assert df._tv_symbol("AKBNK") == "BIST:AKBNK"


# ── _is_special ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sym,expected", [
    ("XAUUSD", True),
    ("xauusd", True),
    ("THYAO", False),
    ("XU100", True),
])
def test_is_special(sym, expected):
    assert df._is_special(sym) is expected


# ── _rand_session ────────────────────────────────────────────────────────────
def test_rand_session_format():
    s = df._rand_session()
    assert s.startswith("qs_")
    assert len(s) == 15   # "qs_" + 12
    assert s[3:].isalnum() and s[3:].islower()
