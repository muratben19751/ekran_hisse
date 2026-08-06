---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance fallback kullanan veri katmanı.
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
`_get_tv_auth_token()` — anonim token; cache'li.

## İlgili
- [[overlay_window]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
