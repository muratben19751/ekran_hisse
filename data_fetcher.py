"""TradingView WebSocket üzerinden gerçek zamanlı fiyat + RSI çeker.

Sembol → servis eşlemeleri `symbols` modülünden (symbols.json) gelir; burada
tekrar tutulmaz. Fiyatlar TV WS ile toplu çekilir; özel semboller (FX/altın/
endeks/kripto) yfinance ile. RSI tek bir WS bağlantısında tüm semboller için
toplu resolve + create_series ile alınır (sembol başına ayrı bağlantı yok).

Not (bilinen optimizasyon fırsatı): fetch_tv_prices/fetch_tv_rsi_bulk her
periyodik yenilemede (fiyat 60sn, RSI 300sn) yeni bir WS bağlantısı açıp
kapatır; her seferinde TCP+TLS handshake + auth + session kurulumu tekrar
ödenir. İşlevsel olarak doğru; ancak TV 'streaming' modunu destekleyen kalıcı
tek bir bağlantı tutmak bu tekrar maliyetini düşürebilir. Şimdilik basitlik ve
sağlamlık için istek-başı bağlantı korunuyor. Bağlantı sızıntısına karşı: her
run_forever ping_interval/ping_timeout ile açılır ve modül genelinde soket
zaman aşımı (_WS_SOCK_TIMEOUT) tanımlıdır; böylece yarı-açık/sessiz bir bağlantı
handshake/recv'de sonsuza kadar bloke kalıp daemon thread'i sızdıramaz.
"""

import json
import math
import random
import re
import string
import threading
import time

import websocket

import config
import symbols as sym_universe
from applog import log

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_SESSION_ID = config.TV_SESSION_ID

# WS soket zaman aşımı: yarı-açık bağlantıda recv'in sonsuza kadar bloke olup
# run_forever thread'ini (ve soketi) sızdırmasını önler. ping_interval/timeout
# ile birlikte, ws.close() sonrası thread'in gerçekten sonlanmasını güvenceler.
_WS_SOCK_TIMEOUT = 12
_WS_PING_INTERVAL = 10
_WS_PING_TIMEOUT = 8
websocket.setdefaulttimeout(_WS_SOCK_TIMEOUT)

_tv_auth_token_cache = [None]
_tv_auth_token_lock  = threading.Lock()
# Negatif (başarısız) sonuç için kısa ömürlü cache: SESSION_ID dolu ama
# disclaimer isteği/regex sürekli başarısızsa, her fiyat (60sn) ve RSI (300sn)
# yenilemesinde 10sn timeout'lu HTTP isteğini tekrarlamak yerine bu süre boyunca
# hızlıca 'unauthorized_user_token' dön. Başarılı token süresizce cache'lenir.
_TV_AUTH_NEG_TTL = 60.0
_tv_auth_neg_until = [0.0]

def _get_tv_auth_token() -> str:
    with _tv_auth_token_lock:
        if _tv_auth_token_cache[0]:
            return _tv_auth_token_cache[0]
        if not TV_SESSION_ID:
            return "unauthorized_user_token"
        # Yakın zamanda başarısız olduysa tekrar HTTP deneme (negatif cache).
        if time.monotonic() < _tv_auth_neg_until[0]:
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
        # Başarısız: negatif sonucu kısa süre cache'le.
        _tv_auth_neg_until[0] = time.monotonic() + _TV_AUTH_NEG_TTL
        return "unauthorized_user_token"


def _invalidate_tv_auth_token() -> None:
    """Pozitif token cache'ini temizle; bir sonraki çağrı yeniden çeker.

    TV session/auth_token sunucu tarafında expire olursa cache eski (geçersiz)
    token'ı süresizce döndürür; WS auth reddedilir ve fiyat/RSI sessizce boş
    döner. Boş sonuç tespit eden fetch fonksiyonları bunu çağırıp bir kez yeniler.
    """
    with _tv_auth_token_lock:
        _tv_auth_token_cache[0] = None
        _tv_auth_neg_until[0] = 0.0


def _rand_id(prefix: str) -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))


def _wrap(msg: dict) -> str:
    s = json.dumps(msg)
    return f"~m~{len(s)}~m~{s}"


def _parse_packets(data: str) -> list:
    return re.findall(r"~m~\d+~m~(.+?)(?=~m~\d+~m~|$)", data)


def fetch_tv_prices(symbols: list) -> dict:
    """TV WebSocket'e bağlan, fiyatları al, kapat. {symbol: (price, chp, vol, avg_vol)}

    Dönen fiyat, gönderilen TAM TV sembolü (ör. 'NYSE:KO') ile orijinal kullanıcı
    sembolüne (ör. 'KO') geri-eşlenir. Böylece aynı ticker'ın farklı borsalardaki
    versiyonları (BIST:KO vs NYSE:KO) çakışmaz; eski split(':')[-1] eşlemesi bunu
    ayırt edemiyordu.

    Sonuç TAMAMEN boşsa (olası: expire olmuş auth token → WS reddi) token cache'i
    bir kez invalide edilip yeniden denenir; ikinci denemede de boşsa boş döner.
    """
    if not symbols:
        return {}
    out = _fetch_tv_prices_once(symbols)
    if not out and TV_SESSION_ID and _tv_auth_token_cache[0]:
        # Cache'lenmiş bir token vardı ama hiç sonuç gelmedi → token expire
        # olmuş olabilir; invalide edip bir kez daha dene.
        log.info("TV fiyat sonucu boş; auth token yenilenip yeniden deneniyor")
        _invalidate_tv_auth_token()
        out = _fetch_tv_prices_once(symbols)
    return out


def _fetch_tv_prices_once(symbols: list) -> dict:
    results = {}
    done_event = threading.Event()
    quote_session = _rand_id("qs_")
    # tam TV sembolü ('NASDAQ:AAPL') → kullanıcı sembolü ('AAPL'). Büyük harfe
    # normalize: TV dönen 'n' alanını da upper'layıp bununla eşleriz.
    tv_to_user = {sym_universe.tv_symbol(s).upper(): s.upper() for s in symbols}
    needed = set(tv_to_user.keys())

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
                sym_full_u = sym_full.upper()
                # Tam TV sembolüyle (borsa prefix'li) geri-eşle; bulunamazsa son
                # parçaya düş (geriye uyum — beklenmedik biçimli 'n' için).
                sym = tv_to_user.get(sym_full_u) or sym_full.split(":")[-1].upper()
                v = p[1].get("v", {})
                lp = v.get("lp")
                price = lp if lp is not None else v.get("last_price")
                pchp  = v.get("chp")
                vol   = v.get("volume")
                avg_vol = v.get("average_volume")
                # NaN savunması: TV WS 'lp'/'last_price' tatil/eksik veri/ilk
                # resolve anında NaN döndürebilir; 'price is not None' NaN'ı
                # geçirir (float('nan') is not None == True) ve NaN fiyat
                # sparkline paint'inde int(vy(nan)) → ValueError ile çöker.
                # yfinance yolundaki math.isnan koruması (aşağıda) ile simetrik.
                price_ok = (
                    price is not None
                    and not (isinstance(price, float) and math.isnan(price))
                )
                if price_ok and sym_full_u in needed:
                    results[sym] = (price, pchp, vol, avg_vol)
                    needed.discard(sym_full_u)
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
    t = threading.Thread(
        target=lambda: ws.run_forever(
            ping_interval=_WS_PING_INTERVAL, ping_timeout=_WS_PING_TIMEOUT
        ),
        daemon=True,
    )
    t.start()
    done_event.wait(timeout=15)
    ws.close()
    return results


# TV interval kodu → dakika sayısı
_TV_INTERVALS = {5: "5", 15: "15", 30: "30", 60: "60"}
_RSI_PERIOD = 14
# RSI için TV'den çekilecek bar sayısı. Wilder yumuşatması bir EMA'dır ve
# ilk basit-ortalama tohumundan sonra oturması için yeterli ısınma (warm-up)
# barı ister. Eski _RSI_PERIOD+10 (=24) bar TV'nin kendi RSI'sinden gözle
# görülür sapıyordu (ort. ~3 puan, uçlarda 15+). ~150 bar ile smoothing oturur
# ve TV değerine yakınsar; tek WS isteğinde ihmal edilebilir ek maliyet.
_RSI_WARMUP_BARS = 150


def _calc_rsi(closes: list, period: int = 14):
    # TV timescale_update tatil/eksik bar için NaN close döndürebilir; NaN'lar
    # temizlenmezse gains/losses NaN olur, guard'lar (==0) NaN'ı yakalamaz ve
    # RSI NaN döner → update_rsi'de int(round(nan)) ValueError. Baştan ele.
    closes = [c for c in closes if isinstance(c, (int, float)) and not math.isnan(c)]
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


def fetch_tv_rsi_bulk(symbols: list, intervals: list = None) -> dict:
    """Tüm semboller için RSI'yı TEK WS bağlantısında toplu çeker.

    Her (sembol, interval) için ayrı bir chart series açar; hepsi aynı bağlantıda
    paralel resolve edilir. Döndürür: {SEMBOL_UPPER: {interval: rsi|None}}.

    Tüm sonuçlar None ise (olası: expire auth token → WS reddi) token cache'i bir
    kez invalide edilip yeniden denenir.
    """
    if intervals is None:
        intervals = [5, 15, 30, 60]
    out = _fetch_tv_rsi_bulk_once(symbols, intervals)
    all_none = all(v is None for d in out.values() for v in d.values()) if out else True
    if all_none and symbols and TV_SESSION_ID and _tv_auth_token_cache[0]:
        log.info("TV RSI sonucu boş; auth token yenilenip yeniden deneniyor")
        _invalidate_tv_auth_token()
        out = _fetch_tv_rsi_bulk_once(symbols, intervals)
    return out


def _fetch_tv_rsi_bulk_once(symbols: list, intervals: list = None) -> dict:
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
                    cs, sid, sid, slot, _TV_INTERVALS[iv], _RSI_WARMUP_BARS
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
        ).run_forever(
            ping_interval=_WS_PING_INTERVAL, ping_timeout=_WS_PING_TIMEOUT
        ),
        daemon=True
    ).start()

    done.wait(timeout=25)
    if ws_ref[0]:
        try:
            ws_ref[0].close()
        except Exception:
            pass
    return results


def fetch_tv_history(symbols: list, interval: int = 5, bars: int = 24) -> dict:
    """Sparkline için gün-içi close serisi çeker (TEK WS bağlantısı).

    Her sembol için tek bir chart series açar (verilen `interval` dakikada,
    `bars` adet bar) ve son `bars` kadar kapanış fiyatını döndürür:
    {SEMBOL_UPPER: [close_eski, ..., close_yeni]} (kronolojik, en yeni sonda).
    Veri yoksa/hata olursa o sembol boş liste ([]) döner.

    RSI ile aynı create_series altyapısını kullanır ama _calc_rsi yerine ham
    close dizisini verir; grafiği gerçek intraday barlarla besler.
    """
    tv_iv = _TV_INTERVALS.get(interval, "5")
    bars = max(2, min(int(bars), 500))
    syms = list(dict.fromkeys(s.upper() for s in symbols))
    if not syms:
        return {}

    results = {s: [] for s in syms}
    cs = _rand_id("cs_")

    series_map = {}       # sid -> SYM
    sym_slot = {}         # SYM -> "sym0", ...
    for i, s in enumerate(syms):
        sym_slot[s] = f"sym{i}"
        series_map[f"{sym_slot[s]}_h"] = s

    pending = set(series_map.keys())
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
            sid = f"{slot}_h"
            ws.send(_wrap({"m": "create_series", "p": [
                cs, sid, sid, slot, tv_iv, bars
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
                    s = series_map.get(sid)
                    if s is None or not isinstance(block, dict):
                        continue
                    bars_data = block.get("s", [])
                    # NaN barları at (tatil/eksik veri); v[4] = close.
                    closes = [
                        b["v"][4] for b in bars_data
                        if len(b.get("v", [])) >= 5
                        and b["v"][4] is not None
                        and not (isinstance(b["v"][4], float) and math.isnan(b["v"][4]))
                    ]
                    if closes:
                        results[s] = closes[-bars:]

            elif m == "series_completed" and len(p) >= 2:
                sid = p[1] if p[1] in series_map else (p[2] if len(p) >= 3 and p[2] in series_map else None)
                if sid:
                    _finish(sid)

            elif m in ("series_error", "symbol_error"):
                for token in p:
                    if isinstance(token, str) and token in series_map:
                        _finish(token)

            elif m == "critical_error":
                log.warning("TV history critical_error: %s", p)
                done.set()

    threading.Thread(
        target=lambda: websocket.WebSocketApp(
            TV_WS_URL,
            header={"Origin": "https://www.tradingview.com"},
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, e: (log.warning("TV history WS hatası: %s", e), done.set()),
            on_close=lambda ws, *_: done.set(),
        ).run_forever(
            ping_interval=_WS_PING_INTERVAL, ping_timeout=_WS_PING_TIMEOUT
        ),
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
            # 5 gün: hafta sonu/tatilde 2 günlük pencere karışık varlıklarda
            # (FX/futures kapalı, kripto açık) yalnızca NaN bar döndürebilir.
            # Daha geniş pencere alıp ticker başına son iki GEÇERLİ kapanışı
            # kullanırız (bkz. aşağıdaki dropna).
            df = yf.download(ticker_syms, period="5d", progress=False, auto_adjust=True)
            closes = df["Close"] if df is not None and not df.empty else None
            # Tek ticker'da df["Close"] bir Series döner (.columns yok); tek
            # sütunlu DataFrame'e çevir ki aşağıdaki 'ts in closes.columns' yolu
            # her iki durumda da çalışsın.
            if closes is not None and getattr(closes, "ndim", 2) == 1:
                closes = closes.to_frame(name=ticker_syms[0])
        except Exception as e:
            log.warning("yfinance özel sembol çekimi hatası: %s", e)
            closes = None
        with lock:
            for s in special_syms:
                ts = sym_universe.yf_ticker(s)
                try:
                    if closes is not None and ts in closes.columns:
                        # NaN barları at, son iki GEÇERLİ kapanışı al.
                        col = closes[ts].dropna()
                        if len(col) >= 2:
                            prev_p = float(col.iloc[-2])
                            price  = float(col.iloc[-1])
                        else:
                            prev_p = price = float("nan")
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
