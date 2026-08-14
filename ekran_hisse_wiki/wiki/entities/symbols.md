---
title: symbols
type: entity
summary: Sembol evreninin tek kaynağı — symbols.json'dan BIST_SYMBOLS/SPECIALS/US_SYMBOLS/KNOWN; fiyat (yfinance) ve RSI (TradingView) ticker eşlemesi tek yerde. 2026-08-14'ten beri ABD hisseleri (NYSE/NASDAQ) desteklenir; çözümleme SPECIALS→BIST→US→fallback önceliğiyle.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
  - sources/04_oturum_2026-08-13.md
  - sources/07_oturum_2026-08-14.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-14
---

# symbols

Sembol evreni ve servis eşlemelerinin **tek kaynağı**. `symbols.json`'dan okur:

- `BIST_SYMBOLS` — eklenebilir tüm BIST sembolleri (liste).
- `SPECIALS` — `{SEMBOL: {"yf": yfinance_ticker, "tv": tradingview_sembol}}`
  (XAUUSD, endeks, FX/kripto vb.).
- `US_SYMBOLS` — **(2026-08-14)** `{TICKER: "NASDAQ"|"NYSE"}` ters harita; ABD
  hisseleri (3684 sembol: NASDAQ 2081 + NYSE 1603). `_load()` `symbols.json`'daki
  `"us": {"NASDAQ":[...], "NYSE":[...]}` bloğundan kurar; bozuk/tanınmayan borsa elenir.
- `KNOWN` — `BIST ∪ SPECIALS`; doğru servis eşlemesi (`tv_symbol`/`yf_ticker`)
  için hâlâ kullanılır. **US evreni KNOWN'a EKLENMEZ** (StockPicker autocomplete'i
  birkaç bin sembolle şişmesin; ekleme zaten evren-kapısız).

Amaç: fiyat (yfinance) ve RSI (TradingView) eşlemesinin iki farklı serviste
tutarlı kalması. DeepR bulgusu G52'nin kökü buydu: `XU050` sembol listesinde
vardı ama `data_fetcher` haritalarında yoktu → tek kaynağa toplandı.

## ABD hisseleri (NYSE + NASDAQ) desteği (2026-08-14)
Kullanıcı ABD hisselerini de takip edebilsin diye `symbols.json`'a `us` bloğu eklendi
(TradingView scanner / `stock_screener` MCP'den, `country=america`, `exclude_otc`).
Prefix'siz yazılan sembol **otomatik çözümlenir**; `tv_symbol`/`yf_ticker` önceliği:

1. **SPECIALS** → `sp["tv"]` / `sp["yf"]` (altın/FX/kripto/endeks).
2. **BIST** → `BIST:<SEM>` / `<SEM>.IS`.
3. **US** → `<BORSA>:<SEM>` (ör. `NASDAQ:AAPL`) / düz `<SEM>` (yfinance, **suffix yok**).
4. **Bilinmeyen** → `BIST:<SEM>` / `<SEM>.IS` (geriye uyum, bozulma yok).

- `tv_symbol("AAPL")="NASDAQ:AAPL"`, `yf_ticker("AAPL")="AAPL"`, `tv_symbol("KO")="NYSE:KO"`.
- **BIST öncelik:** BIST ∩ US kesişimindeki ticker (yalnız `CENTA`) BIST kalır —
  `is_us("CENTA") is False`, `tv_symbol("CENTA")="BIST:CENTA"`. Açık `NASDAQ:`/`NYSE:`
  prefix'li giriş desteği kapsam dışı; nadir çakışmada US versiyonu elle eklenemez.
- Yeni yardımcı `is_us(symbol)` — BIST öncelikli (BIST'te de varsa False).
- **`_load()` artık 3-tuple** döndürür: `(bist, specials, us)`.

ABD hisseleri `is_special` DEĞİLdir → `data_fetcher.fetch_all`'da `bist_syms` grubuna
düşüp **TradingView WS** ile çekilir (TV US destekli); yfinance yolu US'te kullanılmaz.
Bkz. [[data_fetcher]] (tam-sembol eşleme çakışma fix'i).

## Ekleme kısıtı kaldırıldı (2026-08-13)
Eskiden hisse ekleme `is_known` küme kontrolünden geçerdi (yalnız `KNOWN`
eklenebilirdi). Kullanıcı isteğiyle bu kapı kaldırıldı: `overlay._add_from_search`
ve `StockPickerSheet` artık yalnız **biçim** kontrolü yapar (`re.fullmatch
r"[A-Z0-9.\-]{1,20}"`). Listede olmayan sembol de eklenir ve **varsayılan eşlemeyle**
çekilir → TradingView `BIST:<SEM>`, yfinance `<SEM>.IS`. Gerçek değilse fiyat "—"
gelir. `is_known`/`is_special`/`tv_symbol`/`yf_ticker` fonksiyonları özel sembollerin
(altın/FX/endeks) doğru eşlemesi için korunur. Bkz. [[overlay_window]].

## İlgili
- [[data_fetcher]]
- [[architecture_overview]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[known_issues]]
- [[overlay_window]]
<!-- BACKLINKS:END -->
