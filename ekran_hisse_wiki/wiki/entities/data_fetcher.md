---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance bulk-fetch kullanan veri katmanı; auth token thread-safe cache ile korunur.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-07
---

# DataFetcher

`data_fetcher.py`. Fiyat ve RSI verisi için iki ayrı mekanizma.

## fetch_tv_prices(symbols)
TradingView WebSocket quote session açar; `lp`, `chp`, `ch`, `volume`, `average_volume` alanlarını çeker. Sonuç: `{symbol: (price, pct, vol, avg_vol)}`. Timeout: 15 sn.

**Fix (2026-08-07):** `price = lp or last_price` yerine `lp if lp is not None else last_price` kullanılıyor — `0.0` fiyatı artık eksik veri sayılmıyor.

## fetch_all(symbols, callback)
BIST sembollerini `fetch_tv_prices` ile, özel sembolleri tek bir `yf.download()` çağrısıyla çeker. **Eski davranış:** her özel sembol için ayrı thread. **Yeni davranış:** tüm özel semboller tek thread'de `yf.download(tickers, period="2d")` ile toplu çekilir — N HTTP bağlantısı yerine 1.

## fetch_tv_rsi(symbol, intervals)
Ayrı bir TV chart session açar; 5/15/30/60 dk RSI hesaplar. `_calc_rsi()` ile Wilder RSI. Sonuç: `{5: x, 15: x, 30: x, 60: x}`. Bilinmeyen interval değeri artık thread'i çökertmiyor — `_TV_INTERVALS.get(iv)` ile `None` kontrolü yapılır, None ise `done.set()` ile temiz çıkış.

**Silinen:** `_fetch_rsi_one()` — hiç çağrılmayan ölü kod, kaldırıldı.

## TV Auth
`_get_tv_auth_token()` — TradingView `sessionid` çereziyle disclaimer sayfasından `auth_token` kazır. **Thread-safe:** `_tv_auth_token_lock = threading.Lock()` ile tüm check+fetch+store işlemi atomik; paralel WS bağlantılarından N HTTP isteği oluşması engellendi. `sessionid` `config.TV_SESSION_ID` üzerinden git-izlenmeyen `~/.ekranhisse/notes_config.env`'den okunur.

## Bağımlılıklar
`websocket-client` (WS akışı) ve `requests` (auth token) modülün zorunlu bağımlılıklarıdır; `yfinance` özel semboller için kullanılır. Üçü de `requirements.txt`'te listelidir.

## İlgili
- [[overlay_window]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[known_issues]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
