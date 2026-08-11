"""symbols.py — sembol evreni + servis eşlemesi testleri."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import symbols


def test_known_bist_and_special():
    assert symbols.is_known("THYAO")
    assert symbols.is_known("XAUUSD")
    assert not symbols.is_known("ZZZZZ")


def test_is_known_case_insensitive():
    assert symbols.is_known("thyao")
    assert symbols.is_known("Thyao")


def test_is_special():
    assert symbols.is_special("XAUUSD")
    assert symbols.is_special("eurusd")
    assert not symbols.is_special("THYAO")


def test_yf_ticker_bist_default():
    assert symbols.yf_ticker("THYAO") == "THYAO.IS"
    assert symbols.yf_ticker("akbnk") == "AKBNK.IS"


def test_yf_ticker_special():
    assert symbols.yf_ticker("XAUUSD") == "GC=F"
    assert symbols.yf_ticker("EURUSD") == "EURUSD=X"


def test_tv_symbol_bist_default():
    assert symbols.tv_symbol("THYAO") == "BIST:THYAO"


def test_tv_symbol_special():
    assert symbols.tv_symbol("XAUUSD") == "OANDA:XAUUSD"
    assert symbols.tv_symbol("BTCUSD") == "COINBASE:BTCUSD"


def test_known_no_duplicates():
    assert len(symbols.KNOWN) == len(set(symbols.KNOWN))


def test_specials_have_yf_and_tv():
    for sym, m in symbols.SPECIALS.items():
        assert "yf" in m and "tv" in m, sym
