---
title: DataFetcher
type: entity
summary: TradingView WebSocket üzerinden BIST + ABD (NYSE/NASDAQ) fiyatı, RSI ve sparkline intraday bar serisi çeken veri katmanı; TV hesap seri kotası düşük olduğundan RSI/history serileri tek WS'te SIRALI akıtılır (_stream_tv_series), yfinance bulk (FX/altın/kripto), auth token thread-safe cache + boş-sonuçta invalidasyon, NaN/falsy-zero/tam-sembol koruması.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
  - sources/07_oturum_2026-08-14.md
  - sources/09_sparkline_intraday_2026-08-14.md
  - sources/12_tv_seri_limiti_sirali_akis_2026-08-14.md
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

## _stream_tv_series(specs, on_closes, timeout=40) — sıralı seri motoru (2026-08-14)
RSI ve sparkline'ın PAYLAŞTIĞI çekirdek. TV hesabının eşzamanlı-seri kotası düşük
olabilir (bu oturumda ölçüldü: tek session'da aynı anda **1** seri; ikincisi
`exceed limit of series in the session` ile reddedilir). Bu yüzden seriler paralel
değil **sıralı** akıtılır: tek WS'te (handshake+auth bir kez) İLK seri açılır;
`series_completed`/`series_error` gelince `remove_series` ile kapatılır, sonucu
`on_closes(key, closes)` ile yayılır ve BİR SONRAKİ seri açılır. Herhangi bir anda
tek seri açık → kota hiç aşılmaz. `specs = [(key, tv_symbol, tv_iv, bars)]`.

**İki tuzak (canlı probe'da yakalandı):**
1. **Benzersiz slot/sid** — `remove_series` seriyi kaldırır ama resolve edilen
   sembol slotu session'da kalır; aynı slot adını ikinci kez resolve → `duplicate
   id` critical_error. Her seri idx'e bağlı taze isim alır (`sym{idx}`/`s{idx}`).
2. **ws.send kilit dışında** — `state` (idx/closes_acc/cur_sid) `Lock` ile korunur
   ama send senkron işlenip on_message'ı aynı thread'de yeniden çağırabilir; kilit
   içinde send reentrant kilitlenme yapardı. `advancing` bayrağı completed+error
   çift sinyalinde tek ilerleme sağlar. Kaynak:
   `sources/12_tv_seri_limiti_sirali_akis_2026-08-14.md`.

## fetch_tv_rsi_bulk(symbols, intervals)
Her (sembol, interval) için bir chart series; seriler `_stream_tv_series` ile TEK
WS'te SIRALI akıtılır (sembol başına ayrı bağlantı yok, ama seriler paralel de
değil — kota gereği). Sonuç: `{SEMBOL: {5: x, 15: x, 30: x, 60: x}}`. `_calc_rsi()`
Wilder RSI (`_RSI_WARMUP_BARS = 150` ile TV'ye yakınsar). Tüm sonuçlar None ise
(olası expire token) auth token bir kez invalide edilip yeniden denenir (bkz. TV
Auth). **Ödünleşim:** seri başına ~0.75s → RSI süresi sembol sayısıyla lineer
(8 sembol ≈ 17s); arka plan thread'inde, UI bloklanmaz, RSI 300sn'de yenilenir.

## fetch_tv_history(symbols, interval=5, bars=24) — sparkline (2026-08-14)
[[sparkline]] için gün-içi close serisi. RSI ile aynı `_stream_tv_series` motorunu
paylaşır (her sembol = bir seri, sıralı), ama `_calc_rsi` yerine son N ham close
döndürür: `{SEMBOL_UPPER: [close_eski..close_yeni]}`. NaN barları eler.
`overlay._hist_refresh` bunu arka plan thread'de çağırır; `Sparkline.restore()`
gerçek intraday barlarla tohumlanır. Kaynaklar:
`sources/09_sparkline_intraday_2026-08-14.md`,
`sources/12_tv_seri_limiti_sirali_akis_2026-08-14.md`.

## _calc_rsi (2026-08-11)
`avg_gain == 0 and avg_loss == 0` (flat hisse) → `None` döner. Eski davranışta
`100.0` dönüyordu — yanıltıcı aşırı alım sinyali.

## _run_specials_bulk (2026-08-11)
- Dead code `sym_by_ticker` kaldırıldı
- `math.isnan(price) or math.isnan(prev_p) or prev_p == 0` koruması eklendi — NaN UI'a taşınmıyor, ZeroDivision yutulmuyor

## TV Auth
`_get_tv_auth_token()` — TradingView `sessionid` çereziyle disclaimer sayfasından `auth_token` kazır. `_tv_auth_token_lock` ile thread-safe cache; negatif sonuç için kısa TTL cache (60 sn). **Fix (2026-08-14, G64):** pozitif token süresiz cache'leniyordu; token expire olunca fiyat/RSI sessizce boşalıyordu. Artık `_invalidate_tv_auth_token()` var; `fetch_tv_prices`/`fetch_tv_rsi_bulk` tamamen boş sonuçta token'ı bir kez invalide edip yeniden dener. **Not (2026-08-14 netleşti):** "exceed limit
of series in the session" hatasının kök nedeni bu hesabın eşzamanlı-seri kotasının
düşük (≈1) olmasıdır — `TV_SESSION_ID` boş/unauthorized token bunu ağırlaştırır ama
authorized token'la da tek session'da paralel çoklu seri açılamaz. Çözüm token değil
mimari: seriler `_stream_tv_series` ile sıralı açılır (yukarı). Fiyatlar (quote
session) etkilenmez.

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
