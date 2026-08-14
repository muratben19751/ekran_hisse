"""EkranHisse — sembol evreni ve servis eşlemeleri (tek kaynak).

symbols.json'dan okur:
  - BIST_SYMBOLS: eklenebilir tüm BIST sembolleri (liste)
  - SPECIALS:     {SEMBOL: {"yf": yfinance_ticker, "tv": tradingview_sembol}}
  - US_SYMBOLS:   {SEMBOL: "NASDAQ"|"NYSE"} — ABD hisseleri (borsa haritası)
  - KNOWN:        BIST ∪ özel semboller — ekleme doğrulaması bu küme üzerinden

Böylece fiyat (yfinance) ve RSI (TradingView) eşlemesi tek yerde tutulur; biri
güncellenip diğeri unutulamaz. data_fetcher ve overlay buradan okur.

Sembol → borsa çözümleme önceliği (tv_symbol/yf_ticker): SPECIALS → BIST → US →
(bilinmeyen) BIST fallback. Prefix'siz bir US ticker'ı BIST'te de varsa BIST
kazanır (ör. CENTA); nadir durum, açık prefix desteği kapsam dışı.
"""

import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols.json")


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], {}, {}
    bist = [str(s).upper() for s in data.get("bist", []) if isinstance(s, str)]
    specials = {}
    for k, v in data.get("specials", {}).items():
        # Yalnızca 'yf' ve 'tv' değerleri boş-olmayan string olan girdileri al;
        # bozuk (null/boş/tip hatası) girdi sessizce hatalı sorguya yol açmasın.
        if not isinstance(v, dict):
            continue
        yf, tv = v.get("yf"), v.get("tv")
        if isinstance(yf, str) and yf.strip() and isinstance(tv, str) and tv.strip():
            specials[k.upper()] = {"yf": yf.strip(), "tv": tv.strip()}
    # US: {"NASDAQ": [...], "NYSE": [...]} → {TICKER: EXCHANGE} ters harita.
    # Yalnız string ticker + tanınan borsa; bozuk girdi sessizce elenir.
    us = {}
    us_block = data.get("us", {})
    if isinstance(us_block, dict):
        for exch, syms in us_block.items():
            if exch not in ("NASDAQ", "NYSE") or not isinstance(syms, list):
                continue
            for s in syms:
                if isinstance(s, str) and s.strip():
                    us.setdefault(s.strip().upper(), exch)
    return bist, specials, us


BIST_SYMBOLS, SPECIALS, US_SYMBOLS = _load()
# Ekleme doğrulaması: BIST evreni + tüm özel semboller (sıra korunur, tekrarsız).
# US evreni KNOWN'a EKLENMEZ (birkaç bin sembol; ekleme zaten evren-kapısız,
# StockPicker autocomplete'i şişirmemek için).
KNOWN = list(dict.fromkeys(BIST_SYMBOLS + list(SPECIALS.keys())))
_KNOWN_SET = set(KNOWN)
_BIST_SET = set(BIST_SYMBOLS)


def is_known(symbol: str) -> bool:
    return symbol.upper() in _KNOWN_SET


def is_special(symbol: str) -> bool:
    return symbol.upper() in SPECIALS


def is_us(symbol: str) -> bool:
    """Sembol ABD (NASDAQ/NYSE) evreninde mi. BIST önceliği: BIST'te de varsa
    False (BIST kazanır — tv_symbol/yf_ticker ile tutarlı)."""
    s = symbol.upper()
    return s not in _BIST_SET and s in US_SYMBOLS


def yf_ticker(symbol: str) -> str:
    """Sembol → yfinance ticker.

    Öncelik: özel → sp["yf"]; BIST → '<SEMBOL>.IS'; US → düz '<SEMBOL>' (suffix
    yok); bilinmeyen → '<SEMBOL>.IS' (BIST varsayılanı, geriye uyum)."""
    s = symbol.upper()
    sp = SPECIALS.get(s)
    if sp:
        return sp["yf"]
    if s in _BIST_SET:
        return f"{s}.IS"
    if s in US_SYMBOLS:
        return s
    return f"{s}.IS"


def tv_symbol(symbol: str) -> str:
    """Sembol → TradingView adresi.

    Öncelik: özel → sp["tv"]; BIST → 'BIST:<SEMBOL>'; US → '<BORSA>:<SEMBOL>'
    (ör. 'NASDAQ:AAPL'); bilinmeyen → 'BIST:<SEMBOL>' (geriye uyum)."""
    s = symbol.upper()
    sp = SPECIALS.get(s)
    if sp:
        return sp["tv"]
    if s in _BIST_SET:
        return f"BIST:{s}"
    exch = US_SYMBOLS.get(s)
    if exch:
        return f"{exch}:{s}"
    return f"BIST:{s}"
