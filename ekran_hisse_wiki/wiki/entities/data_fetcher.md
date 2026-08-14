---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST + ABD (NYSE/NASDAQ) fiyatı, RSI ve sparkline için intraday bar serisi çeken, yfinance bulk-fetch (FX/altın/kripto) kullanan veri katmanı; auth token thread-safe cache + boş-sonuçta invalidasyon, NaN/ZeroDivision, falsy-zero ve tam-sembol eşleme koruması içerir.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
  - sources/07_oturum_2026-08-14.md
  - sources/09_sparkline_intraday_2026-08-14.md
last_updated: 2026-08-14
---

# DataFetcher

`data_fetcher.py`. Fiyat, RSI ve sparkline intraday bar verisi için ayrı mekanizmalar.

## fetch_tv_prices(symbols)
TradingView WebSocket quote session açar; `lp`, `chp`, `ch`, `volume`, `average_volume` alanlarını çeker. Sonuç: `{symbol: (price, pct, vol, avg_vol)}`. Timeout: 15 sn.

**Fix (2026-08-07):** `price = lp or last_price` → `lp if lp is not None else last_price` — `0.0` fiyatı eksik veri sayılmıyordu; düzeltildi.
**Fix (2026-08-11):** `if price` → `if price is not None` — `0.0` fiyatlı semboller artık `needed` setinden çıkarılıyor, 15 sn timeout tetiklenmiyor.
**Fix (2026-08-14 — tam-sembol eşleme):** Dönen fiyat eskiden `sym_full.split(":")[-1]` ile eşlenirdi; `NYSE:KO` ve `BIST:KO` ikisi de `"KO"`ya çökerdi (borsa çakışması). Artık `on_open`'da gönderilen tam TV sembolü → kullanıcı sembolü haritası (`{tv_symbol(s).upper(): s.upper()}`) tutulur; `on_message` dönen tam `n` (prefix'li) ile geri-eşler, `needed` seti tam TV sembolü bazlıdır. ABD hisse desteğinin (bkz. [[symbols]]) ön koşulu. Beklenmedik biçimli `n` için `split(":")[-1]` fallback korunur.

## fetch_all(symbols, callback)
BIST **ve ABD** sembollerini `fetch_tv_prices` ile (ikisi de `is_special` DEĞİL → `bist_syms` grubu, TV WS US destekli), özel sembolleri (FX/altın/endeks/kripto) tek bir `yf.download()` çağrısıyla çeker. Tüm özel semboller tek thread'de toplu çekilir — N HTTP bağlantısı yerine 1. (`_run_bist` adı tarihsel; ABD hisseleri de bu daldan gider.)

## fetch_tv_rsi_bulk(symbols, intervals)
Tüm semboller için RSI'yı TEK WS bağlantısında toplu çeker (sembol başına ayrı
bağlantı yok); her (sembol, interval) için bir chart series. Sonuç:
`{SEMBOL: {5: x, 15: x, 30: x, 60: x}}`. `_calc_rsi()` Wilder RSI (`_RSI_WARMUP_BARS
= 150` ile TV'ye yakınsar). Tüm sonuçlar None ise (olası expire token) auth token
bir kez invalide edilip yeniden denenir (bkz. TV Auth).

## fetch_tv_history(symbols, interval=5, bars=24) — sparkline (2026-08-14)
[[sparkline]] için gün-içi close serisi. RSI'ın `create_series` altyapısını
paylaşır (tek WS, `resolve_symbol` + `create_series`), ama `_calc_rsi` yerine son N
ham close döndürür: `{SEMBOL_UPPER: [close_eski..close_yeni]}`. NaN barları eler.
`overlay._hist_refresh` bunu arka plan thread'de çağırır; `Sparkline.restore()`
gerçek intraday barlarla tohumlanır. Kaynak:
`sources/09_sparkline_intraday_2026-08-14.md`.

## _calc_rsi (2026-08-11)
`avg_gain == 0 and avg_loss == 0` (flat hisse) → `None` döner. Eski davranışta
`100.0` dönüyordu — yanıltıcı aşırı alım sinyali.

## _run_specials_bulk (2026-08-11)
- Dead code `sym_by_ticker` kaldırıldı
- `math.isnan(price) or math.isnan(prev_p) or prev_p == 0` koruması eklendi — NaN UI'a taşınmıyor, ZeroDivision yutulmuyor

## TV Auth
`_get_tv_auth_token()` — TradingView `sessionid` çereziyle disclaimer sayfasından `auth_token` kazır. `_tv_auth_token_lock` ile thread-safe cache; negatif sonuç için kısa TTL cache (60 sn). **Fix (2026-08-14, G64):** pozitif token süresiz cache'leniyordu; token expire olunca fiyat/RSI sessizce boşalıyordu. Artık `_invalidate_tv_auth_token()` var; `fetch_tv_prices`/`fetch_tv_rsi_bulk` tamamen boş sonuçta token'ı bir kez invalide edip yeniden dener. **Not:** `TV_SESSION_ID` boşken unauthorized token çoklu-sembol RSI'da "exceed limit of series in the session" verebilir (fiyatlar etkilenmez); session ID ile limit artar.

## Bağımlılıklar
`websocket-client`, `requests`, `yfinance` — `requirements.txt`'te listeleniyor.

## İlgili
- [[overlay_window]]
- [[stock_row]]
- [[sparkline]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[known_issues]]
- [[overlay_window]]
- [[sparkline]]
- [[stock_row]]
- [[symbols]]
<!-- BACKLINKS:END -->
