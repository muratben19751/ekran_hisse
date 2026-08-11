"""EkranHisse — sembol evreni ve servis eşlemeleri (tek kaynak).

symbols.json'dan okur:
  - BIST_SYMBOLS: eklenebilir tüm BIST sembolleri (liste)
  - SPECIALS:     {SEMBOL: {"yf": yfinance_ticker, "tv": tradingview_sembol}}
  - KNOWN:        BIST ∪ özel semboller — ekleme doğrulaması bu küme üzerinden

Böylece fiyat (yfinance) ve RSI (TradingView) eşlemesi tek yerde tutulur; biri
güncellenip diğeri unutulamaz. data_fetcher ve overlay buradan okur.
"""

import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols.json")


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], {}
    bist = [str(s).upper() for s in data.get("bist", []) if isinstance(s, str)]
    specials = {}
    for k, v in data.get("specials", {}).items():
        if isinstance(v, dict) and "yf" in v and "tv" in v:
            specials[k.upper()] = {"yf": v["yf"], "tv": v["tv"]}
    return bist, specials


BIST_SYMBOLS, SPECIALS = _load()
# Ekleme doğrulaması: BIST evreni + tüm özel semboller (sıra korunur, tekrarsız)
KNOWN = list(dict.fromkeys(BIST_SYMBOLS + list(SPECIALS.keys())))
_KNOWN_SET = set(KNOWN)


def is_known(symbol: str) -> bool:
    return symbol.upper() in _KNOWN_SET


def is_special(symbol: str) -> bool:
    return symbol.upper() in SPECIALS


def yf_ticker(symbol: str) -> str:
    """Sembol → yfinance ticker. Özel değilse '<SEMBOL>.IS' (BIST varsayılanı)."""
    s = symbol.upper()
    sp = SPECIALS.get(s)
    return sp["yf"] if sp else f"{s}.IS"


def tv_symbol(symbol: str) -> str:
    """Sembol → TradingView adresi. Özel değilse 'BIST:<SEMBOL>'."""
    s = symbol.upper()
    sp = SPECIALS.get(s)
    return sp["tv"] if sp else f"BIST:{s}"
