"""TradingView WebSocket üzerinden gerçek zamanlı fiyat + RSI çeker.

Sembol → servis eşlemeleri `symbols` modülünden (symbols.json) gelir; burada
tekrar tutulmaz. Fiyatlar TV WS ile toplu çekilir; özel semboller (FX/altın/
endeks/kripto) yfinance ile. RSI tek bir WS bağlantısında tüm semboller için
toplu resolve + create_series ile alınır (sembol başına ayrı bağlantı yok).
"""

import json
import math
import random
import re
import string
import threading

import websocket

import config
import symbols as sym_universe
from applog import log

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_SESSION_ID = config.TV_SESSION_ID

_tv_auth_token_cache = [None]
_tv_auth_token_lock  = threading.Lock()

def _get_tv_auth_token() -> str:
    with _tv_auth_token_lock:
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
        except Exception as e:
            log.warning("TV auth token alınamadı: %s", e)
        return "unauthorized_user_token"


def _rand_id(prefix: str) -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


def _wrap(msg: dict) -> str:
    s = json.dumps(msg)
    return f"~m~{len(s)}~m~{s}"


def _parse_packets(data: str) -> list:
    return re.findall(r"~m~\d+~m~(.+?)(?=~m~\d+~m~|$)", data)


def fetch_tv_prices(symbols: list) -> dict:
    """TV WebSocket'e bağlan, fiyatları al, kapat. {symbol: (price, chp, vol, avg_vol)}"""
    results = {}
    done_event = threading.Event()
    needed = set(s.upper() for s in symbols)
    quote_session = _rand_id("qs_")

    def on_open(ws):
        token = _get_tv_auth_token()
        ws.send(_wrap({"m": "set_auth_token", "p": [token]}))
        ws.send(_wrap({"m": "quote_create_session", "p": [quote_session]}))
        ws.send(_wrap({"m": "quote_set_fields",
                        "p": [quote_session, "lp", "chp", "ch", "volume", "average_volume"]}))
        for s in symbols:
            ws.send(_wrap({"m": "quote_add_symbols", "p": [quote_session, sym_universe.tv_symbol(s)]}))

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
                lp = v.get("lp")
                price = lp if lp is not None else v.get("last_price")
                pchp  = v.get("chp")
                vol   = v.get("volume")
                avg_vol = v.get("average_volume")
                if price is not None and sym in needed:
                    results[sym] = (price, pchp, vol, avg_vol)
                    needed.discard(sym)
                    if not needed:
                        done_event.set()

    def on_error(ws, err):
        log.warning("TV fiyat WS hatası: %s", err)
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
    if avg_gain == 0 and avg_loss == 0:
        return None  # hareketsiz hisse: RSI tanımsız
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def fetch_tv_rsi(symbol: str, intervals: list = None) -> dict:
    """Tek sembol için RSI. (Geriye dönük uyumluluk — içeride bulk çağırır.)"""
    if intervals is None:
        intervals = [5, 15, 30, 60]
    out = fetch_tv_rsi_bulk([symbol], intervals)
    return out.get(symbol.upper(), {iv: None for iv in intervals})


def fetch_tv_rsi_bulk(symbols: list, intervals: list = None) -> dict:
    """Tüm semboller için RSI'yı TEK WS bağlantısında toplu çeker.

    Her (sembol, interval) için ayrı bir chart series açar; hepsi aynı bağlantıda
    paralel resolve edilir. Döndürür: {SEMBOL_UPPER: {interval: rsi|None}}.
    """
    if intervals is None:
        intervals = [5, 15, 30, 60]
    intervals = [iv for iv in intervals if iv in _TV_INTERVALS]
    syms = list(dict.fromkeys(s.upper() for s in symbols))
    if not syms or not intervals:
        return {s: {iv: None for iv in intervals} for s in syms}

    results = {s: {iv: None for iv in intervals} for s in syms}
    cs = _rand_id("cs_")

    # series_id → (symbol, interval); sembol → tanıtıcı (resolve adı)
    series_map = {}       # sid -> (SYM, iv)
    sym_slot = {}         # SYM -> "sym0", "sym1", ...
    for i, s in enumerate(syms):
        sym_slot[s] = f"sym{i}"
    for s in syms:
        for iv in intervals:
            series_map[f"{sym_slot[s]}_{iv}"] = (s, iv)

    pending = set(series_map.keys())   # tamamlanmayı bekleyen seriler
    done = threading.Event()
    ws_ref = [None]
    lock = threading.Lock()

    def on_open(ws):
        ws_ref[0] = ws
        token = _get_tv_auth_token()
        ws.send(_wrap({"m": "set_auth_token", "p": [token]}))
        ws.send(_wrap({"m": "chart_create_session", "p": [cs, ""]}))
        for s in syms:
            slot = sym_slot[s]
            ws.send(_wrap({"m": "resolve_symbol", "p": [
                cs, slot, f'={{"symbol":"{sym_universe.tv_symbol(s)}","adjustment":"splits"}}'
            ]}))
            for iv in intervals:
                sid = f"{slot}_{iv}"
                ws.send(_wrap({"m": "create_series", "p": [
                    cs, sid, sid, slot, _TV_INTERVALS[iv], _RSI_PERIOD + 10
                ]}))

    def _finish(sid):
        with lock:
            pending.discard(sid)
            if not pending:
                done.set()

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

            if m == "timescale_update" and len(p) >= 2 and isinstance(p[1], dict):
                for sid, block in p[1].items():
                    entry = series_map.get(sid)
                    if entry is None or not isinstance(block, dict):
                        continue
                    s, iv = entry
                    bars = block.get("s", [])
                    closes = [b["v"][4] for b in bars if len(b.get("v", [])) >= 5]
                    if closes:
                        results[s][iv] = _calc_rsi(closes)

            elif m == "series_completed" and len(p) >= 2:
                # p = [cs, series_id, 'streaming', ...] veya [cs, series_id]
                sid = p[1] if p[1] in series_map else (p[2] if len(p) >= 3 and p[2] in series_map else None)
                if sid:
                    _finish(sid)

            elif m in ("series_error", "symbol_error"):
                # Bu seriyi(leri) beklemeyi bırak; hangileri olduğu p içinde
                for token in p:
                    if isinstance(token, str) and token in series_map:
                        _finish(token)

            elif m == "critical_error":
                log.warning("TV RSI critical_error: %s", p)
                done.set()

    threading.Thread(
        target=lambda: websocket.WebSocketApp(
            TV_WS_URL,
            header={"Origin": "https://www.tradingview.com"},
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, e: (log.warning("TV RSI WS hatası: %s", e), done.set()),
            on_close=lambda ws, *_: done.set(),
        ).run_forever(),
        daemon=True
    ).start()

    done.wait(timeout=25)
    if ws_ref[0]:
        try:
            ws_ref[0].close()
        except Exception:
            pass
    return results


def fetch_all(symbols: list, callback) -> None:
    """Fiyatları çeker; bittiğinde callback(list[dict]) çağrılır.

    callback HER durumda bir kez çağrılır (hata/exception olsa da) — böylece
    UI'daki 'Güncelleniyor…' kilidi asla kalıcı olmaz.
    """
    if not symbols:
        callback([])
        return

    bist_syms    = [s for s in symbols if not sym_universe.is_special(s)]
    special_syms = [s for s in symbols if sym_universe.is_special(s)]

    results = {}
    lock = threading.Lock()
    total = (1 if bist_syms else 0) + len(special_syms)
    remaining = [total]
    fired = [False]

    def _maybe_done():
        # lock çağıran taraf tutuyor
        remaining[0] -= 1
        if remaining[0] <= 0 and not fired[0]:
            fired[0] = True
            out = [results.get(s, {"symbol": s, "price": None, "change_pct": None}) for s in symbols]
            try:
                callback(out)
            except Exception as e:
                log.warning("fetch_all callback hatası: %s", e)

    def _run_bist():
        try:
            data = fetch_tv_prices(bist_syms)
        except Exception as e:
            log.warning("BIST fiyat çekimi hatası: %s", e)
            data = {}
        with lock:
            for s in bist_syms:
                if s.upper() in data:
                    price, pct, vol, avg_vol = data[s.upper()]
                    results[s] = {"symbol": s, "price": price, "change_pct": pct,
                                  "volume": vol, "avg_volume": avg_vol}
                else:
                    results[s] = {"symbol": s, "price": None, "change_pct": None,
                                  "volume": None, "avg_volume": None}
            _maybe_done()

    def _run_specials_bulk():
        ticker_syms = [sym_universe.yf_ticker(s) for s in special_syms]
        closes = None
        try:
            import yfinance as yf
            df = yf.download(ticker_syms, period="2d", progress=False, auto_adjust=True)
            closes = df["Close"].iloc[-2:] if len(df) >= 2 else None
        except Exception as e:
            log.warning("yfinance özel sembol çekimi hatası: %s", e)
            closes = None
        with lock:
            for s in special_syms:
                ts = sym_universe.yf_ticker(s)
                try:
                    if closes is not None and ts in closes.columns:
                        prev_p = float(closes[ts].iloc[-2])
                        price  = float(closes[ts].iloc[-1])
                        if math.isnan(price) or math.isnan(prev_p) or prev_p == 0:
                            results[s] = {"symbol": s, "price": None, "change_pct": None}
                        else:
                            results[s] = {"symbol": s, "price": price,
                                          "change_pct": (price - prev_p) / prev_p * 100}
                    else:
                        results[s] = {"symbol": s, "price": None, "change_pct": None}
                except Exception:
                    results[s] = {"symbol": s, "price": None, "change_pct": None}
                _maybe_done()

    if bist_syms:
        threading.Thread(target=_run_bist, daemon=True).start()
    if special_syms:
        threading.Thread(target=_run_specials_bulk, daemon=True).start()
