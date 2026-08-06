---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance fallback kullanan veri katmanı; sessionid env'den okunur.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-06
---

# DataFetcher

`data_fetcher.py`. Fiyat ve RSI verisi için iki ayrı mekanizma.

## fetch_tv_prices(symbols)
TradingView WebSocket quote session açar; `lp`, `chp`, `ch`, `volume`, `average_volume` alanlarını çeker. Sonuç: `{symbol: (price, pct, vol, avg_vol)}`. Timeout: 20 sn.

## fetch_all(symbols, callback)
BIST sembollerini `fetch_tv_prices` ile, özel sembolleri (XAUUSD vb.) yfinance ile paralel çeker. Callback'e `[{symbol, price, change_pct, volume, avg_volume}]` listesi iletir.

## fetch_tv_rsi(symbol, intervals)
Ayrı bir TV chart session açar; 5/15/30/60 dk RSI hesaplar. `_calc_rsi()` ile Wilder RSI. Sonuç: `{5: x, 15: x, 30: x, 60: x}`.

## TV Auth
`_get_tv_auth_token()` — TradingView `sessionid` çereziyle disclaimer sayfasından `auth_token` kazır; cache'li. **`sessionid` artık kodda hardcoded değil**; `config.TV_SESSION_ID` üzerinden git-izlenmeyen `notes_config.env`'den okunur. Boşsa `unauthorized_user_token`'a düşer (anonim/kısıtlı erişim). Bkz: [[architecture_overview]] güvenlik notu.

## Bağımlılıklar
`websocket-client` (WS akışı) ve `requests` (auth token) modülün zorunlu bağımlılıklarıdır; `yfinance` yalnızca fallback sembollerde kullanılır. Üçü de `requirements.txt`'te listelidir.

## İlgili
- [[overlay_window]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
