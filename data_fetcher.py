import threading
import yfinance as yf

# Doğrudan yfinance ticker'ına map'lenen özel semboller
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
}


def _resolve_ticker(symbol: str) -> str:
    upper = symbol.upper()
    if upper in _SYMBOL_MAP:
        return _SYMBOL_MAP[upper]
    # 6 haneli forex çifti (örn. EURUSD) → yfinance forex formatı
    if len(upper) == 6 and upper.isalpha():
        return f"{upper}=X"
    return f"{upper}.IS"


def get_stock_info(symbol: str):
    try:
        ticker_sym = _resolve_ticker(symbol)
        ticker = yf.Ticker(ticker_sym)
        fi = ticker.fast_info
        price = fi.last_price
        prev = fi.previous_close
        if price is None or prev is None or prev == 0:
            return None
        pct = (price - prev) / prev * 100
        return {"symbol": symbol, "price": price, "change_pct": pct}
    except Exception:
        return None


def fetch_all(symbols: list[str], callback) -> None:
    """Fetch all symbols concurrently, then call callback(results)."""
    if not symbols:
        callback([])
        return

    results = [None] * len(symbols)
    remaining = [len(symbols)]
    lock = threading.Lock()

    def _fetch_one(i, sym):
        info = get_stock_info(sym)
        results[i] = info if info else {"symbol": sym, "price": None, "change_pct": None}
        with lock:
            remaining[0] -= 1
            if remaining[0] == 0:
                callback(results)

    for i, sym in enumerate(symbols):
        threading.Thread(target=_fetch_one, args=(i, sym), daemon=True).start()
