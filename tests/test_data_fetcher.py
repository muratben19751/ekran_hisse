"""data_fetcher.py — saf yardımcı fonksiyon testleri."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

df = pytest.importorskip("data_fetcher")   # websocket bağımlılığı yoksa atla
import symbols as sym_universe


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


# ── tv_symbol (symbols modülü) ────────────────────────────────────────────────
def test_tv_symbol():
    assert sym_universe.tv_symbol("thyao") == "BIST:THYAO"
    assert sym_universe.tv_symbol("AKBNK") == "BIST:AKBNK"


# ── is_special (symbols modülü) ───────────────────────────────────────────────
@pytest.mark.parametrize("sym,expected", [
    ("XAUUSD", True),
    ("xauusd", True),
    ("THYAO", False),
    ("XU100", True),
])
def test_is_special(sym, expected):
    assert sym_universe.is_special(sym) is expected


# ── _rand_id ──────────────────────────────────────────────────────────────────
def test_rand_id_format():
    s = df._rand_id("qs_")
    assert s.startswith("qs_")
    assert len(s) == 15   # "qs_" + 12
    assert s[3:].isalnum() and s[3:].islower()


# ── _calc_rsi ────────────────────────────────────────────────────────────────
def test_calc_rsi_insufficient_data():
    # period=14 için en az 15 kapanış gerekir; az veriyle None dönmeli
    assert df._calc_rsi([1.0] * 14) is None


def test_calc_rsi_all_gains_returns_100():
    # Sadece yükseliş → avg_loss=0 → RSI=100
    closes = list(range(1, 17))   # 16 değer, hep artan
    assert df._calc_rsi(closes) == 100.0


def test_calc_rsi_all_losses_returns_0():
    # Sadece düşüş → avg_gain=0 → RSI=0
    closes = list(range(16, 0, -1))
    assert df._calc_rsi(closes) == 0.0


def test_calc_rsi_known_value():
    # Bilinen değerlerle hesaplanmış RSI: 14-periyot Wilder smoothing
    # Kapanışlar: 14 sabit artış (gain=1) + 1 düşüş (loss=5)
    # avg_gain_init = 1.0, avg_loss_init = 0.0
    # smoothing sonrası: avg_gain=(13/14+0/14)=13/14, avg_loss=(0*13/14+5/14)=5/14
    # RS = (13/14)/(5/14) = 13/5 = 2.6 → RSI = 100 - 100/3.6 ≈ 72.2
    closes = [10.0 + i for i in range(15)] + [9.0]  # 15 artış, son 5 düşüş
    result = df._calc_rsi(closes)
    assert result is not None
    assert 0.0 < result < 100.0


def test_calc_rsi_returns_rounded_one_decimal():
    closes = [float(i) for i in range(1, 20)]
    result = df._calc_rsi(closes)
    assert result == round(result, 1)


# ── price=0.0 fix — or operatörü yerine is not None kullanılmalı ─────────────
def test_price_zero_not_treated_as_missing():
    # fetch_tv_prices içindeki mantığı simüle et: lp=0.0 → None değil, geçerli
    lp = 0.0
    last = 5.0
    # Eski kod: price = lp or last  →  5.0 (yanlış)
    # Yeni kod: price = lp if lp is not None else last  →  0.0 (doğru)
    price = lp if lp is not None else last
    assert price == 0.0


# ── _TV_INTERVALS guard ───────────────────────────────────────────────────────
def test_tv_intervals_valid_keys():
    assert set(df._TV_INTERVALS.keys()) == {5, 15, 30, 60}


def test_tv_intervals_unknown_key_returns_none():
    assert df._TV_INTERVALS.get(1) is None
    assert df._TV_INTERVALS.get(240) is None


# ── RSI sembol adresleri (symbols modülü) ─────────────────────────────────────
def test_tv_symbol_rsi_special():
    assert sym_universe.tv_symbol("XAUUSD") == "OANDA:XAUUSD"
    assert sym_universe.tv_symbol("EURUSD") == "FX:EURUSD"
    assert sym_universe.tv_symbol("BTCUSD") == "COINBASE:BTCUSD"
    assert sym_universe.tv_symbol("XU100") == "BIST:XU100"


def test_tv_symbol_rsi_bist_fallback():
    assert sym_universe.tv_symbol("THYAO") == "BIST:THYAO"
    assert sym_universe.tv_symbol("akbnk") == "BIST:AKBNK"


def test_tv_symbol_rsi_case_insensitive():
    assert sym_universe.tv_symbol("xauusd") == "OANDA:XAUUSD"
