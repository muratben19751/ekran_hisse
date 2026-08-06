"""TradingView WebSocket üzerinden gerçek zamanlı fiyat çeker."""

import json
import random
import re
import string
import threading
import time

import websocket

import config

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_SESSION_ID = config.TV_SESSION_ID

_tv_auth_token_cache = [None]

def _get_tv_auth_token() -> str:
    if _tv_auth_token_cache[0]:
        return _tv_auth_token_cache[0]
    if not TV_SESSION_ID:
        return "unauthorized_user_token"
    try:
        import requests
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

# RSI için TV'deki doğru sembol adresleri
_TV_RSI_SYMBOL_MAP = {
    "XAUUSD": "OANDA:XAUUSD",
    "XAGUSD": "OANDA:XAGUSD",
    "XTIUSD": "OANDA:XTIUSD",
    "EURUSD": "FX:EURUSD",
    "GBPUSD": "FX:GBPUSD",
    "USDJPY": "FX:USDJPY",
    "USDTRY": "FX:USDTRY",
    "BTCUSD": "COINBASE:BTCUSD",
    "ETHUSD": "COINBASE:ETHUSD",
    "DXY":    "TVC:DXY",
    "SP500":  "SP:SPX",
    "NASDAQ": "NASDAQ:NDX",
    "DOW":    "DJ:DJI",
    "XU100":  "BIST:XU100",
    "XU030":  "BIST:XU030",
    "XBANK":  "BIST:XBANK",
    "XUSIN":  "BIST:XUSIN",
    "XHOLD":  "BIST:XHOLD",
    "XTCRT":  "BIST:XTCRT",
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


def _tv_symbol_for_rsi(symbol: str) -> str:
    return _TV_RSI_SYMBOL_MAP.get(symbol.upper(), f"BIST:{symbol.upper()}")


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
                        "p": [quote_session, "lp", "chp", "ch", "volume", "average_volume"]}))
        for sym in symbols:
            ws.send(_wrap({"m": "quote_add_symbols", "p": [quote_session, _tv_symbol(sym)]}))

    def on_message(ws, message):
        for raw in _parse_packets(message):
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
                pchp  = v.get("chp")
                vol   = v.get("volume")
                avg_vol = v.get("average_volume")
                if price and sym in needed:
                    results[sym] = (price, pchp, vol, avg_vol)
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


# TV interval kodu → dakika sayısı
_TV_INTERVALS = {5: "5", 15: "15", 30: "30", 60: "60"}
_RSI_PERIOD = 14


def _calc_rsi(closes: list, period: int = 14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def _fetch_rsi_one(tv_sym: str, interval: int) -> float:
    """Tek interval için TV'den bar çekip RSI döndürür."""
    result = [None]
    done = threading.Event()
    cs = "cs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    sid = "s1"

    def on_open(ws):
        token = _get_tv_auth_token()
        ws.send(_wrap({"m": "set_auth_token", "p": [token]}))
        ws.send(_wrap({"m": "chart_create_session", "p": [cs, ""]}))
        ws.send(_wrap({"m": "resolve_symbol", "p": [
            cs, "sym", f'={{"symbol":"{tv_sym}","adjustment":"splits"}}'
        ]}))
        ws.send(_wrap({"m": "create_series", "p": [
            cs, sid, sid, "sym", str(_TV_INTERVALS[interval]), _RSI_PERIOD + 10
        ]}))

    def on_message(ws, message):
        for raw in _parse_packets(message):
            if raw.startswith("~h~"):
                ws.send(f"~m~{len(raw)}~m~{raw}")
                continue
            try:
                pkt = json.loads(raw)
            except Exception:
                continue
            m = pkt.get("m")
            p = pkt.get("p", [])
            if m == "timescale_update" and len(p) >= 2 and sid in p[1]:
                bars = p[1][sid].get("s", [])
                closes = [b["v"][4] for b in bars if len(b.get("v", [])) >= 5]
                if closes:
                    result[0] = _calc_rsi(closes)
            if m == "series_completed":
                done.set()
            if m in ("critical_error", "series_error", "symbol_error"):
                done.set()

    ws = websocket.WebSocketApp(
        TV_WS_URL,
        header={"Origin": "https://www.tradingview.com"},
        on_open=on_open,
        on_message=on_message,
        on_error=lambda ws, e: done.set(),
        on_close=lambda ws, *_: done.set(),
    )
    threading.Thread(target=ws.run_forever, daemon=True).start()
    done.wait(timeout=12)
    ws.close()
    return result[0]


def fetch_tv_rsi(symbol: str, intervals: list = None) -> dict:
    """Tek WS bağlantısında sembolü resolve edip her interval'ı sırayla çeker."""
    if intervals is None:
        intervals = [5, 15, 30, 60]
    tv_sym = _tv_symbol_for_rsi(symbol)
    results = {iv: None for iv in intervals}
    cs = "cs_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    # Her interval sırayla işlenecek; WS açık kalır
    iv_queue = list(intervals)
    current = [0]   # şu an işlenen index
    done = threading.Event()
    ws_ref = [None]

    def _request_next(ws):
        if current[0] >= len(iv_queue):
            done.set()
            return
        # Önceki seriyi sil
        if current[0] > 0:
            prev_iv = iv_queue[current[0] - 1]
            ws.send(_wrap({"m": "remove_series", "p": [cs, f"s{prev_iv}"]}))
        iv = iv_queue[current[0]]
        sid = f"s{iv}"
        ws.send(_wrap({"m": "create_series", "p": [
            cs, sid, sid, "sym", str(_TV_INTERVALS[iv]), _RSI_PERIOD + 10
        ]}))

    def on_open(ws):
        ws_ref[0] = ws
        token = _get_tv_auth_token()
        ws.send(_wrap({"m": "set_auth_token", "p": [token]}))
        ws.send(_wrap({"m": "chart_create_session", "p": [cs, ""]}))
        ws.send(_wrap({"m": "resolve_symbol", "p": [
            cs, "sym", f'={{"symbol":"{tv_sym}","adjustment":"splits"}}'
        ]}))

    def on_message(ws, message):
        for raw in _parse_packets(message):
            if raw.startswith("~h~"):
                ws.send(f"~m~{len(raw)}~m~{raw}")
                continue
            try:
                pkt = json.loads(raw)
            except Exception:
                continue
            m = pkt.get("m")
            p = pkt.get("p", [])

            if m == "symbol_resolved":
                _request_next(ws)

            elif m == "timescale_update" and len(p) >= 2:
                iv = iv_queue[current[0]] if current[0] < len(iv_queue) else None
                if iv is None:
                    continue
                sid = f"s{iv}"
                if sid in p[1]:
                    bars = p[1][sid].get("s", [])
                    closes = [b["v"][4] for b in bars if len(b.get("v", [])) >= 5]
                    if closes:
                        results[iv] = _calc_rsi(closes)

            elif m == "series_completed":
                iv = iv_queue[current[0]] if current[0] < len(iv_queue) else None
                sid = f"s{iv}" if iv else ""
                # p = [cs, series_name, 'streaming', ...]
                if len(p) >= 2 and (p[1] == sid or (len(p) >= 3 and p[2] == sid)):
                    current[0] += 1
                    if current[0] >= len(iv_queue):
                        done.set()
                    else:
                        _request_next(ws)

            elif m in ("critical_error", "series_error", "symbol_error"):
                done.set()

    threading.Thread(
        target=lambda: websocket.WebSocketApp(
            TV_WS_URL,
            header={"Origin": "https://www.tradingview.com"},
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, e: done.set(),
            on_close=lambda ws, *_: done.set(),
        ).run_forever(),
        daemon=True
    ).start()

    done.wait(timeout=20)
    if ws_ref[0]:
        ws_ref[0].close()
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
                    price, pct, vol, avg_vol = data[sym.upper()]
                    results[sym] = {"symbol": sym, "price": price, "change_pct": pct,
                                    "volume": vol, "avg_volume": avg_vol}
                else:
                    results[sym] = {"symbol": sym, "price": None, "change_pct": None,
                                    "volume": None, "avg_volume": None}
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

