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


def test_specials_have_nonempty_string_yf_tv():
    # _load artık boş/tip-hatalı yf/tv değerlerini eler; kalan hepsi geçerli str
    for sym, m in symbols.SPECIALS.items():
        assert isinstance(m["yf"], str) and m["yf"].strip(), sym
        assert isinstance(m["tv"], str) and m["tv"].strip(), sym


# ── _load: bozuk symbols.json girdilerini ele ─────────────────────────────────
def test_load_rejects_invalid_special_entries(tmp_path, monkeypatch):
    import json
    bad = tmp_path / "symbols.json"
    bad.write_text(json.dumps({
        "bist": ["THYAO", "AKBNK", 123],          # 123 (str değil) elenmeli
        "specials": {
            "GOOD":     {"yf": "GC=F",  "tv": "OANDA:XAUUSD"},
            "NULL_YF":  {"yf": None,     "tv": "X:Y"},   # elenmeli
            "EMPTY_TV": {"yf": "A=B",    "tv": "  "},     # elenmeli
            "MISSING":  {"yf": "A=B"},                     # tv yok → elenmeli
            "NOT_DICT": "string-değil",                    # elenmeli
        },
    }), encoding="utf-8")
    monkeypatch.setattr(symbols, "_PATH", str(bad))
    bist, specials, us = symbols._load()
    assert bist == ["THYAO", "AKBNK"]              # 123 elendi
    assert set(specials.keys()) == {"GOOD"}        # yalnızca geçerli girdi
    assert specials["GOOD"] == {"yf": "GC=F", "tv": "OANDA:XAUUSD"}
    assert us == {}                                 # us bloğu yoksa boş


# ── US (NASDAQ/NYSE) evreni + çözümleme ───────────────────────────────────────
def test_tv_symbol_us():
    assert symbols.tv_symbol("AAPL") == "NASDAQ:AAPL"
    assert symbols.tv_symbol("KO") == "NYSE:KO"


def test_yf_ticker_us_no_suffix():
    # US hissesi yfinance'ta prefix'siz/suffix'siz düz ticker
    assert symbols.yf_ticker("AAPL") == "AAPL"
    assert symbols.yf_ticker("KO") == "KO"


def test_us_priority_bist_first():
    # BIST ∩ US kesişimindeki ticker (CENTA) BIST kazanır — karar #2 önceliği
    assert "CENTA" in symbols.BIST_SYMBOLS
    assert symbols.tv_symbol("CENTA") == "BIST:CENTA"
    assert symbols.yf_ticker("CENTA") == "CENTA.IS"
    assert not symbols.is_us("CENTA")


def test_is_us():
    assert symbols.is_us("AAPL")
    assert symbols.is_us("aapl")            # case-insensitive
    assert not symbols.is_us("THYAO")       # BIST
    assert not symbols.is_us("XAUUSD")      # special
    assert not symbols.is_us("ZZZZZ")       # bilinmeyen


def test_unknown_still_bist_fallback():
    # US'te de BIST'te de olmayan → mevcut BIST fallback (geriye uyum, bozulma yok)
    assert symbols.tv_symbol("ZZZZZ") == "BIST:ZZZZZ"
    assert symbols.yf_ticker("ZZZZZ") == "ZZZZZ.IS"


def test_us_not_in_known():
    # US evreni KNOWN'a eklenmez (StockPicker autocomplete şişmesin)
    assert not symbols.is_known("AAPL")


def test_load_parses_and_reverses_us_block(tmp_path, monkeypatch):
    import json
    p = tmp_path / "symbols.json"
    p.write_text(json.dumps({
        "bist": ["THYAO"],
        "specials": {},
        "us": {
            "NASDAQ": ["AAPL", "MSFT", 123],       # 123 elenmeli
            "NYSE": ["KO", "  ", ""],               # boş/whitespace elenmeli
            "AMEX": ["SEB"],                         # tanınmayan borsa → elenmeli
            "BADVAL": "liste-değil",                 # elenmeli
        },
    }), encoding="utf-8")
    monkeypatch.setattr(symbols, "_PATH", str(p))
    _bist, _specials, us = symbols._load()
    assert us == {"AAPL": "NASDAQ", "MSFT": "NASDAQ", "KO": "NYSE"}
