"""TradingView WebSocket üzerinden gerçek zamanlı fiyat çeker."""

import json
import random
import re
import string
import threading
import time

import websocket

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_SESSION_ID = "osbbjahxxdb3k4bw6sf4momoema3rtef"

_tv_auth_token_cache = [None]

def _get_tv_auth_token() -> str:
    if _tv_auth_token_cache[0]:
        return _tv_auth_token_cache[0]
    try:
        import requests, re
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        s.cookies.set("sessionid", TV_SESSION_ID, domain=".tradingview.com")
        r = s.get("https://www.tradingview.com/disclaimer/", timeout=10)
        m = re.search(r'"auth_token":"([^"]+)"', r.text)
        if m:
            _tv_auth_token_cache[0] = m.group(1)
            return _tv_auth_token_cache[0]
    except Exception:
        pass
    return "unauthorized_user_token"

# BIST dışı semboller için yfinance fallback
_SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "XTIUSD": "CL=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "USDTRY": "TRY=X",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "DXY":    "DX-Y.NYB",
    "SP500":  "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW":    "^DJI",
    "XU100":  "XU100.IS",
    "XU030":  "XU030.IS",
    "XBANK":  "XBANK.IS",
    "XUSIN":  "XUSIN.IS",
    "XHOLD":  "XHOLD.IS",
    "XTCRT":  "XTCRT.IS",
}


def _is_special(symbol: str) -> bool:
    return symbol.upper() in _SYMBOL_MAP


def _rand_session():
    return "qs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


def _wrap(msg: dict) -> str:
    s = json.dumps(msg)
    return f"~m~{len(s)}~m~{s}"


def _parse_packets(data: str) -> list:
    return re.findall(r"~m~\d+~m~(.+?)(?=~m~\d+~m~|$)", data)


def _tv_symbol(symbol: str) -> str:
    return f"BIST:{symbol.upper()}"


def fetch_tv_prices(symbols: list) -> dict:
    """TV WebSocket'e bağlan, fiyatları al, kapat. {symbol: (price, change_pct)}"""
    results = {}
    done_event = threading.Event()
    needed = set(s.upper() for s in symbols)
    quote_session = _rand_session()

    def on_open(ws):
        token = _get_tv_auth_token()
        ws.send(_wrap({"m": "set_auth_token", "p": [token]}))
        ws.send(_wrap({"m": "quote_create_session", "p": [quote_session]}))
        ws.send(_wrap({"m": "quote_set_fields",
                        "p": [quote_session, "lp", "chp", "ch"]}))
        for sym in symbols:
            ws.send(_wrap({"m": "quote_add_symbols", "p": [quote_session, _tv_symbol(sym)]}))

    def on_message(ws, message):
        for raw in _parse_packets(message):
            # Heartbeat
            if raw.startswith("~h~"):
                ws.send(f"~m~{len(raw)}~m~{raw}")
                continue
            try:
                pkt = json.loads(raw)
            except Exception:
                continue
            if pkt.get("m") == "qsd":
                p = pkt.get("p", [])
                if len(p) < 2:
                    continue
                sym_full = p[1].get("n", "")
                sym = sym_full.split(":")[-1].upper()
                v = p[1].get("v", {})
                price = v.get("lp") or v.get("last_price")
                pch   = v.get("ch")   # absolute change
                pchp  = v.get("chp")  # percent change
                if price and sym in needed:
                    results[sym] = (price, pchp)
                    needed.discard(sym)
                    if not needed:
                        done_event.set()

    def on_error(ws, err):
        done_event.set()

    def on_close(ws, *_):
        done_event.set()

    ws = websocket.WebSocketApp(
        TV_WS_URL,
        header={"Origin": "https://www.tradingview.com"},
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    t = threading.Thread(target=lambda: ws.run_forever(), daemon=True)
    t.start()
    done_event.wait(timeout=15)
    ws.close()
    return results


def _fetch_yfinance(symbol: str):
    try:
        import yfinance as yf
        ticker_sym = _SYMBOL_MAP.get(symbol.upper(), f"{symbol.upper()}.IS")
        fi = yf.Ticker(ticker_sym).fast_info
        price, prev = fi.last_price, fi.previous_close
        if price is None or not prev:
            return None
        return {"symbol": symbol, "price": price, "change_pct": (price - prev) / prev * 100}
    except Exception:
        return None


def fetch_all(symbols: list, callback) -> None:
    if not symbols:
        callback([])
        return

    bist_syms    = [s for s in symbols if not _is_special(s)]
    special_syms = [s for s in symbols if _is_special(s)]

    results = {}
    lock = threading.Lock()
    total = (1 if bist_syms else 0) + len(special_syms)
    remaining = [total]

    def _maybe_done():
        remaining[0] -= 1
        if remaining[0] == 0:
            out = [results.get(s, {"symbol": s, "price": None, "change_pct": None}) for s in symbols]
            callback(out)

    def _run_bist():
        data = fetch_tv_prices(bist_syms)
        with lock:
            for sym in bist_syms:
                if sym.upper() in data:
                    price, pct = data[sym.upper()]
                    results[sym] = {"symbol": sym, "price": price, "change_pct": pct}
                else:
                    results[sym] = {"symbol": sym, "price": None, "change_pct": None}
            _maybe_done()

    def _run_special(sym):
        info = _fetch_yfinance(sym)
        with lock:
            results[sym] = info if info else {"symbol": sym, "price": None, "change_pct": None}
            _maybe_done()

    if bist_syms:
        threading.Thread(target=_run_bist, daemon=True).start()
    for sym in special_syms:
        threading.Thread(target=_run_special, args=(sym,), daemon=True).start()
