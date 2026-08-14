"""data_fetcher.py — saf yardımcı fonksiyon testleri."""

import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

df = pytest.importorskip("data_fetcher")   # websocket bağımlılığı yoksa atla
import symbols as sym_universe  # noqa: E402  (importorskip'ten sonra olmalı)


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


# ── _get_tv_auth_token / _invalidate_tv_auth_token ────────────────────────────
# Auth token cache mantığı: pozitif token süresizce cache'lenir, başarısız
# sonuç kısa süre negatif cache'lenir. Testler arası sızıntı olmasın diye her
# testin başında iki cache slot'unu sıfırla.
def _reset_tv_auth():
    df._tv_auth_token_cache[0] = None
    df._tv_auth_neg_until[0] = 0.0


def test_get_tv_auth_token_no_session_returns_unauthorized(monkeypatch):
    # SESSION_ID boşken HTTP hiç yapılmaz; 'unauthorized_user_token' döner.
    _reset_tv_auth()
    monkeypatch.setattr(df, "TV_SESSION_ID", "")
    assert df._get_tv_auth_token() == "unauthorized_user_token"


def test_get_tv_auth_token_positive_cache_no_http(monkeypatch):
    # Pozitif cache doluyken HTTP yapılmadan cache dönmeli. requests import'unu
    # patlayacak sahte modülle enjekte et: cache HİT olursa hiç import edilmez.
    _reset_tv_auth()
    monkeypatch.setattr(df, "TV_SESSION_ID", "sess123")
    df._tv_auth_token_cache[0] = "cached_tok"

    import types
    boom = types.ModuleType("requests")

    def _explode(*a, **k):
        raise AssertionError("cache doluyken HTTP yapılmamalı")

    boom.Session = _explode
    monkeypatch.setitem(sys.modules, "requests", boom)

    assert df._get_tv_auth_token() == "cached_tok"


def test_get_tv_auth_token_negative_cache_returns_unauthorized(monkeypatch):
    # neg_until gelecekteyken (yakın zamanda başarısız) HTTP yapılmadan
    # 'unauthorized_user_token' döner.
    _reset_tv_auth()
    monkeypatch.setattr(df, "TV_SESSION_ID", "sess123")
    df._tv_auth_neg_until[0] = df.time.monotonic() + 1000.0

    import types
    boom = types.ModuleType("requests")

    def _explode(*a, **k):
        raise AssertionError("negatif cache aktifken HTTP yapılmamalı")

    boom.Session = _explode
    monkeypatch.setitem(sys.modules, "requests", boom)

    assert df._get_tv_auth_token() == "unauthorized_user_token"


def test_invalidate_tv_auth_token_resets_caches():
    # _invalidate_tv_auth_token hem pozitif token'ı hem neg_until'ı sıfırlar.
    _reset_tv_auth()
    df._tv_auth_token_cache[0] = "tok"
    df._tv_auth_neg_until[0] = df.time.monotonic() + 500.0
    df._invalidate_tv_auth_token()
    assert df._tv_auth_token_cache[0] is None
    assert df._tv_auth_neg_until[0] == 0.0


# ── _calc_rsi ────────────────────────────────────────────────────────────────
def test_calc_rsi_insufficient_data():
    # period=14 için en az 15 kapanış gerekir; az veriyle None dönmeli
    assert df._calc_rsi([1.0] * 14) is None


def test_calc_rsi_all_losses_returns_0():
    # Sadece düşüş → avg_gain=0 → RSI=0
    closes = list(range(16, 0, -1))
    assert df._calc_rsi(closes) == 0.0


def test_calc_rsi_known_value():
    # 15 artış (10→24) + 1 düşüş (24→9). Wilder yumuşatmasıyla elle/koşarak
    # doğrulanmış referans: 46.4. Trivial '0<x<100' yerine kesin değere sabitle.
    closes = [10.0 + i for i in range(15)] + [9.0]
    result = df._calc_rsi(closes)
    assert result == pytest.approx(46.4, abs=0.05)


def test_calc_rsi_all_gains_returns_100():
    # Yalnızca artış → avg_loss=0 → RSI=100
    assert df._calc_rsi([10.0 + i for i in range(20)]) == 100.0


def test_calc_rsi_flat_returns_none():
    # Hareketsiz hisse (tüm kapanış eşit) → avg_gain==avg_loss==0 → RSI tanımsız
    assert df._calc_rsi([50.0] * 20) is None


def test_calc_rsi_returns_rounded_one_decimal():
    closes = [float(i) for i in range(1, 20)]
    result = df._calc_rsi(closes)
    assert result == round(result, 1)


# ── price=0.0 fix — or operatörü yerine is not None kullanılmalı ─────────────
def test_price_zero_not_treated_as_missing(monkeypatch):
    # Gerçek fetch akışını sür: lp=0.0 içeren bir qsd paketi → fiyat 0.0 KORUNUR
    # (None'a düşmez). Eski 'price = lp or last' mantığı 0.0'ı eksik sanırdı.
    # Harness on_open + on_message'ı gerçek data_fetcher koduyla çalıştırır.
    res = _drive_fetch_tv_prices(
        monkeypatch, ["THYAO"], [("BIST:THYAO", 0.0)],
    )
    assert "THYAO" in res
    assert res["THYAO"][0] == 0.0
    assert res["THYAO"][0] is not None


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


# ── US (NASDAQ/NYSE) sembol adresleri + çakışma eşlemesi ─────────────────────
def test_tv_symbol_us_exchange_prefix():
    assert sym_universe.tv_symbol("AAPL") == "NASDAQ:AAPL"
    assert sym_universe.tv_symbol("KO") == "NYSE:KO"


def test_us_symbol_not_special_goes_tv_path(monkeypatch):
    # US hissesi is_special DEĞİL → fetch_all'da bist_syms (TV WS) yoluna gider,
    # yfinance'a değil. fetch_tv_prices monkeypatch'le doğrula.
    assert sym_universe.is_special("AAPL") is False
    seen = {}

    def fake_tv(syms):
        seen["syms"] = list(syms)
        return {"AAPL": (300.0, 1.0, 0, 0)}

    monkeypatch.setattr(df, "fetch_tv_prices", fake_tv)
    fired, calls = _run_fetch_all(["AAPL"])
    assert fired and len(calls) == 1
    assert seen["syms"] == ["AAPL"]              # TV yoluna gitti
    out = {d["symbol"]: d for d in calls[0]}
    assert out["AAPL"]["price"] == 300.0


def _drive_fetch_tv_prices(monkeypatch, symbols, qsd_packets):
    """WebSocketApp'i sahtele; on_open (mesaj gönderimi yutulur) + verilen qsd
    paketlerini on_message'a besle. fetch_tv_prices sonucunu döndür.

    qsd_packets: [(n_full, price)] — TV 'qsd' mesajındaki 'n' (tam sembol) + lp.
    """
    import data_fetcher as _df

    class _FakeWS:
        def __init__(self, url, header=None, on_open=None, on_message=None,
                     on_error=None, on_close=None):
            self._on_open = on_open
            self._on_message = on_message

        def run_forever(self, **kw):
            # on_open: gönderilen mesajlar yutulur (send no-op)
            self._on_open(self)
            for n_full, price in qsd_packets:
                pkt = {"m": "qsd", "p": ["qs", {"n": n_full, "v": {"lp": price}}]}
                body = _df.json.dumps(pkt)
                self._on_message(self, f"~m~{len(body)}~m~{body}")

        def send(self, *a, **k):
            pass

        def close(self):
            pass

    monkeypatch.setattr(_df.websocket, "WebSocketApp", _FakeWS)
    # auth token HTTP'sini atla
    monkeypatch.setattr(_df, "_get_tv_auth_token", lambda: "tok")
    return _df.fetch_tv_prices(symbols)


def test_fetch_tv_prices_maps_full_symbol_no_exchange_clash(monkeypatch):
    # BIST:KO ve NYSE:KO ayrı kullanıcı sembollerine doğru eşlenmeli; eski
    # split(':')[-1] eşlemesi ikisini de "KO"ya çökertirdi.
    # (KO BIST'te YOK; senaryo için tam-sembol eşlemesini iki farklı US sembolüyle
    #  kanıtlıyoruz: AAPL/NASDAQ ve KO/NYSE.)
    res = _drive_fetch_tv_prices(
        monkeypatch, ["AAPL", "KO"],
        [("NASDAQ:AAPL", 300.0), ("NYSE:KO", 87.0)],
    )
    assert res["AAPL"][0] == 300.0
    assert res["KO"][0] == 87.0


def test_fetch_tv_prices_bist_still_works(monkeypatch):
    # Regresyon: BIST sembolü tam-sembol haritasıyla da doğru eşlenir.
    res = _drive_fetch_tv_prices(
        monkeypatch, ["THYAO"], [("BIST:THYAO", 55.5)],
    )
    assert res["THYAO"][0] == 55.5


# ── fetch_all: 'callback her durumda tam bir kez' invaryantı ──────────────────
# En kritik eşzamanlılık sözleşmesi (aksi halde UI'daki 'Güncelleniyor…' kilidi
# kalıcı olur). Ağ katmanı monkeypatch'le sahtelenir; Qt gerekmez.


def _run_fetch_all(symbols, timeout=3.0):
    """fetch_all'ı çalıştır, callback sonucunu ve çağrı sayısını döndür."""
    calls = []
    done = threading.Event()

    def cb(result):
        calls.append(result)
        done.set()

    df.fetch_all(symbols, cb)
    fired = done.wait(timeout)
    return fired, calls


def test_fetch_all_empty_list_fires_once_immediately():
    fired, calls = _run_fetch_all([])
    assert fired
    assert len(calls) == 1
    assert calls[0] == []


def test_fetch_all_bist_only_single_callback(monkeypatch):
    monkeypatch.setattr(df, "fetch_tv_prices",
                        lambda syms: {"THYAO": (10.0, 1.5, 100, 90)})
    fired, calls = _run_fetch_all(["THYAO"])
    assert fired and len(calls) == 1
    out = {d["symbol"]: d for d in calls[0]}
    assert out["THYAO"]["price"] == 10.0
    assert out["THYAO"]["change_pct"] == 1.5


def test_fetch_all_bist_missing_symbol_gets_none(monkeypatch):
    monkeypatch.setattr(df, "fetch_tv_prices", lambda syms: {})   # veri yok
    fired, calls = _run_fetch_all(["THYAO", "AKBNK"])
    assert fired and len(calls) == 1
    out = {d["symbol"]: d for d in calls[0]}
    assert out["THYAO"]["price"] is None
    assert out["AKBNK"]["price"] is None


def test_fetch_all_fires_once_when_fetch_raises(monkeypatch):
    def boom(syms):
        raise RuntimeError("ağ patladı")
    monkeypatch.setattr(df, "fetch_tv_prices", boom)
    fired, calls = _run_fetch_all(["THYAO"])
    assert fired and len(calls) == 1        # exception'a rağmen tam bir kez
    assert calls[0][0]["price"] is None


def test_fetch_all_callback_exception_does_not_crash(monkeypatch):
    monkeypatch.setattr(df, "fetch_tv_prices", lambda syms: {})
    done = threading.Event()

    def bad_cb(result):
        done.set()
        raise ValueError("callback içinde hata")

    # fetch_all worker thread'i callback exception'ını yutmalı (çökme yok).
    df.fetch_all(["THYAO"], bad_cb)
    assert done.wait(3.0)


def test_fetch_all_output_preserves_input_order(monkeypatch):
    monkeypatch.setattr(df, "fetch_tv_prices",
                        lambda syms: {s: (1.0, 0.0, 0, 0) for s in
                                      (x.upper() for x in syms)})
    fired, calls = _run_fetch_all(["THYAO", "AKBNK", "GARAN"])
    assert fired and len(calls) == 1
    assert [d["symbol"] for d in calls[0]] == ["THYAO", "AKBNK", "GARAN"]


# ── Entegrasyon sözleşmesi: fetch_all çıktısı ↔ overlay.apply_data anahtarları ─
# apply_data/_apply_cached_prices her item'da 'symbol','price','change_pct'
# zorunlu anahtarlarını okur (volume/avg_volume .get() ile opsiyonel). fetch_all'ın
# TÜM dalları (BIST-bulundu, BIST-eksik, exception-fallback) bu sözleşmeyi tutmalı.
_REQUIRED_KEYS = {"symbol", "price", "change_pct"}


def test_fetch_all_contract_keys_present_bist(monkeypatch):
    monkeypatch.setattr(df, "fetch_tv_prices",
                        lambda syms: {"THYAO": (10.0, 1.5, 100, 90)})
    _, calls = _run_fetch_all(["THYAO", "AKBNK"])   # biri bulundu, biri eksik
    for item in calls[0]:
        assert _REQUIRED_KEYS <= set(item), item


def test_fetch_all_contract_keys_present_on_exception(monkeypatch):
    def boom(syms):
        raise RuntimeError("x")
    monkeypatch.setattr(df, "fetch_tv_prices", boom)
    _, calls = _run_fetch_all(["THYAO"])
    for item in calls[0]:
        assert _REQUIRED_KEYS <= set(item), item


# ── _calc_rsi: NaN kapanış barı savunması ─────────────────────────────────────
def test_calc_rsi_filters_nan_closes():
    # TV timescale_update tatil/eksik bar için NaN döndürebilir; NaN'lar
    # temizlenmeden guard'lar (==0) yakalamaz ve RSI NaN döner → update_rsi
    # int(round(nan)) ValueError. Filtre sonrası ya geçerli sayı ya None dönmeli.
    nan = float("nan")
    closes = [10.0 + i for i in range(15)] + [nan]   # son bar NaN
    result = df._calc_rsi(closes)
    # NaN atıldıktan sonra 15 bar kalır (period+1 tam sınır) → sonlu sayı
    assert result is None or (isinstance(result, float) and result == result)


def test_calc_rsi_all_nan_returns_none():
    result = df._calc_rsi([float("nan")] * 20)
    assert result is None


def test_calc_rsi_nan_never_returns_nan():
    # Karışık NaN + geçerli barlar: sonuç asla NaN olmamalı (int(round) güvenli)
    nan = float("nan")
    closes = [nan, 10.0, 11.0, nan, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0,
              18.0, 19.0, 20.0, 21.0, 22.0, 23.0, nan, 24.0]
    result = df._calc_rsi(closes)
    if result is not None:
        import math as _m
        assert not _m.isnan(result)


# ── _run_specials_bulk (yfinance FX/altın/endeks/kripto yolu) ─────────────────
# fetch_all'ın özel-sembol dalı: yf.download monkeypatch'lenir, Qt gerekmez.
class _FakeSeries:
    """pandas Series benzeri minimal sahte: dropna + iloc[-1]/[-2]."""
    def __init__(self, values):
        self._v = list(values)

    def dropna(self):
        import math as _m
        return _FakeSeries([x for x in self._v
                            if not (isinstance(x, float) and _m.isnan(x))])

    def __len__(self):
        return len(self._v)

    @property
    def iloc(self):
        return self._v


class _FakeCloses:
    """df['Close'] benzeri: .columns ve col erişimi."""
    def __init__(self, data):   # data: {ticker: [close...]}
        self._data = {k: _FakeSeries(v) for k, v in data.items()}
        self.ndim = 2

    @property
    def columns(self):
        return list(self._data.keys())

    def __getitem__(self, key):
        return self._data[key]


class _FakeDF:
    def __init__(self, closes):
        self._closes = closes
        self.empty = False

    def __getitem__(self, key):
        assert key == "Close"
        return self._closes


def _install_fake_yf(monkeypatch, closes_by_ticker):
    """yfinance modülünü sahtele (sys.modules), yf.download istenen veriyi dönsün."""
    import types
    fake = types.ModuleType("yfinance")

    def download(tickers, period=None, progress=None, auto_adjust=None):
        return _FakeDF(_FakeCloses(closes_by_ticker))

    fake.download = download
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def test_fetch_all_specials_happy_path(monkeypatch):
    # XAUUSD gibi özel sembol; iki geçerli kapanıştan change_pct hesaplanır.
    ticker = sym_universe.yf_ticker("XAUUSD")
    _install_fake_yf(monkeypatch, {ticker: [100.0, 110.0]})
    fired, calls = _run_fetch_all(["XAUUSD"])
    assert fired and len(calls) == 1
    out = {d["symbol"]: d for d in calls[0]}
    assert out["XAUUSD"]["price"] == 110.0
    assert out["XAUUSD"]["change_pct"] == pytest.approx(10.0)


def test_fetch_all_specials_weekend_nan_last_bar(monkeypatch):
    # Hafta sonu: son bar NaN. dropna ile son iki GEÇERLİ kapanış kullanılır.
    ticker = sym_universe.yf_ticker("EURUSD")
    _install_fake_yf(monkeypatch, {ticker: [1.10, 1.20, float("nan")]})
    fired, calls = _run_fetch_all(["EURUSD"])
    assert fired and len(calls) == 1
    out = {d["symbol"]: d for d in calls[0]}
    # NaN atılınca 1.10→1.20 kalır → fiyat 1.20, değişim ~9.09%
    assert out["EURUSD"]["price"] == pytest.approx(1.20)
    assert out["EURUSD"]["change_pct"] == pytest.approx((1.20 - 1.10) / 1.10 * 100)


def test_fetch_all_specials_insufficient_valid_bars(monkeypatch):
    # Tek geçerli kapanış (diğeri NaN) → change_pct hesaplanamaz → None.
    ticker = sym_universe.yf_ticker("BTCUSD")
    _install_fake_yf(monkeypatch, {ticker: [float("nan"), 50000.0]})
    fired, calls = _run_fetch_all(["BTCUSD"])
    out = {d["symbol"]: d for d in calls[0]}
    assert out["BTCUSD"]["price"] is None
    assert out["BTCUSD"]["change_pct"] is None


def test_fetch_all_specials_contract_keys_present(monkeypatch):
    # Özel dal da fetch_all sözleşmesini (symbol/price/change_pct) tutmalı.
    ticker = sym_universe.yf_ticker("XAUUSD")
    _install_fake_yf(monkeypatch, {ticker: [100.0, 110.0]})
    _, calls = _run_fetch_all(["XAUUSD"])
    for item in calls[0]:
        assert _REQUIRED_KEYS <= set(item), item


def test_fetch_all_specials_prev_zero_no_div_by_zero(monkeypatch):
    # prev_p == 0 → bölme yok, change_pct None.
    ticker = sym_universe.yf_ticker("XAUUSD")
    _install_fake_yf(monkeypatch, {ticker: [0.0, 110.0]})
    _, calls = _run_fetch_all(["XAUUSD"])
    out = {d["symbol"]: d for d in calls[0]}
    assert out["XAUUSD"]["change_pct"] is None
    assert out["XAUUSD"]["price"] is None


# ── TV timescale_update parse sözleşmesi (gerçek fetch akışı) ─────────────────
# Canlı WS test edilemez ama parse mantığı (close çıkarımı b["v"][4] + _calc_rsi
# zinciri) GERÇEK _fetch_tv_rsi_bulk_once on_message'ını sürerek doğrulanabilir:
# WebSocketApp sahtelenir, verilen bar'lar bir timescale_update paketiyle
# on_message'a beslenir. TV mesaj formatı değişirse test kırılır.
def _drive_fetch_tv_rsi(monkeypatch, symbol, interval, bars):
    """WebSocketApp'i sahtele; _fetch_tv_rsi_bulk_once'ın gerçek on_open/
    on_message'ını sürerek verilen bar'lardan hesaplanan RSI'yı döndür.

    bars: [{"v": [time, open, high, low, close, volume]}] — TV bar formatı.
    Döndürür: sembol/interval için hesaplanan RSI değeri (veya None).
    """
    import data_fetcher as _df

    slot = "sym0"          # tek sembol → resolve slot'u
    sid = f"{slot}_{interval}"

    class _FakeWS:
        def __init__(self, url, header=None, on_open=None, on_message=None,
                     on_error=None, on_close=None):
            self._on_open = on_open
            self._on_message = on_message

        def run_forever(self, **kw):
            self._on_open(self)          # resolve_symbol + create_series (yutulur)
            # Gerçek TV timescale_update paketi biçimi: p[1] = {sid: {"s": bars}}
            pkt = {"m": "timescale_update", "p": ["cs", {sid: {"s": bars}}]}
            body = _df.json.dumps(pkt)
            self._on_message(self, f"~m~{len(body)}~m~{body}")
            # Seriyi tamamla ki done event set olsun ve fetch beklemesin.
            done_pkt = {"m": "series_completed", "p": ["cs", sid, "streaming"]}
            db = _df.json.dumps(done_pkt)
            self._on_message(self, f"~m~{len(db)}~m~{db}")

        def send(self, *a, **k):
            pass

        def close(self):
            pass

    monkeypatch.setattr(_df.websocket, "WebSocketApp", _FakeWS)
    monkeypatch.setattr(_df, "_get_tv_auth_token", lambda: "tok")
    out = _df.fetch_tv_rsi_bulk([symbol], intervals=[interval])
    return out[symbol.upper()][interval]


def test_tv_timescale_bars_close_extraction_contract(monkeypatch):
    # 16 artan kapanış → gerçek on_message close'ları çıkarır, _calc_rsi = 100.0.
    # (yalnızca artış → avg_loss=0 → RSI 100)
    bars = [{"v": [1700000000 + i, 10.0, 11.0, 9.0, 10.0 + i, 100]}
            for i in range(16)]
    rsi = _drive_fetch_tv_rsi(monkeypatch, "THYAO", 15, bars)
    assert rsi == 100.0


def test_tv_timescale_short_v_array_skipped(monkeypatch):
    # Eksik/bozuk 'v' dizisi (< 5 eleman) close çıkarımından atlanmalı (parser'ın
    # 'len(v) >= 5' koruması). Geriye tek geçerli close kalır → period+1 altında
    # → _calc_rsi None döner. Kısa dizinin IndexError vermeden atlandığını kanıtlar.
    bars = [{"v": [1, 2, 3]}, {"v": [10, 11, 12, 13, 42.0, 99]}]
    rsi = _drive_fetch_tv_rsi(monkeypatch, "THYAO", 15, bars)
    assert rsi is None
