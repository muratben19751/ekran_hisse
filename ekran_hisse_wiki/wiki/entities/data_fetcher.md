---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance bulk-fetch kullanan veri katmanı; auth token thread-safe cache, NaN/ZeroDivision ve falsy-zero koruması içerir.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
last_updated: 2026-08-11
---

# DataFetcher

`data_fetcher.py`. Fiyat ve RSI verisi için iki ayrı mekanizma.

## fetch_tv_prices(symbols)
TradingView WebSocket quote session açar; `lp`, `chp`, `ch`, `volume`, `average_volume` alanlarını çeker. Sonuç: `{symbol: (price, pct, vol, avg_vol)}`. Timeout: 15 sn.

**Fix (2026-08-07):** `price = lp or last_price` → `lp if lp is not None else last_price` — `0.0` fiyatı eksik veri sayılmıyordu; düzeltildi.
**Fix (2026-08-11):** `if price` → `if price is not None` — `0.0` fiyatlı semboller artık `needed` setinden çıkarılıyor, 15 sn timeout tetiklenmiyor.

## fetch_all(symbols, callback)
BIST sembollerini `fetch_tv_prices` ile, özel sembolleri tek bir `yf.download()` çağrısıyla çeker. Tüm özel semboller tek thread'de toplu çekilir — N HTTP bağlantısı yerine 1.

## fetch_tv_rsi(symbol, intervals)
Ayrı bir TV chart session açar; 5/15/30/60 dk RSI hesaplar. `_calc_rsi()` ile Wilder RSI. Sonuç: `{5: x, 15: x, 30: x, 60: x}`.

## _calc_rsi (2026-08-11)
`avg_gain == 0 and avg_loss == 0` (flat hisse) → `None` döner. Eski davranışta `100.0` dönüyordu — yanıltıcı aşırı alım sinyali.

## _run_specials_bulk (2026-08-11)
- Dead code `sym_by_ticker` kaldırıldı
- `math.isnan(price) or math.isnan(prev_p) or prev_p == 0` koruması eklendi — NaN UI'a taşınmıyor, ZeroDivision yutulmuyor

## TV Auth
`_get_tv_auth_token()` — TradingView `sessionid` çereziyle disclaimer sayfasından `auth_token` kazır. `_tv_auth_token_lock` ile thread-safe cache. **Açık sorun:** token süresi dolunca cache temizlenmez; uygulama yeniden başlatılmalı.

## Bağımlılıklar
`websocket-client`, `requests`, `yfinance` — `requirements.txt`'te listeleniyor.

## İlgili
- [[overlay_window]]
- [[stock_row]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[known_issues]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
