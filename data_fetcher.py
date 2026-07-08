import threading
import yfinance as yf


def get_stock_info(symbol: str):
    """Fetch price and daily % change for a BIST symbol (e.g. 'THYAO')."""
    try:
        ticker = yf.Ticker(f"{symbol}.IS")
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
    """Fetch all symbols in a background thread, then call callback(results)."""
    def _run():
        results = []
        for sym in symbols:
            info = get_stock_info(sym)
            results.append(info if info else {"symbol": sym, "price": None, "change_pct": None})
        callback(results)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
