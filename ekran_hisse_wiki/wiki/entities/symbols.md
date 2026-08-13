---
title: symbols
type: entity
summary: Sembol evreninin tek kaynağı — symbols.json'dan BIST_SYMBOLS/SPECIALS/KNOWN; fiyat (yfinance) ve RSI (TradingView) ticker eşlemesi tek yerde. 2026-08-13'ten beri ekleme is_known ile kısıtlı DEĞİL — her geçerli biçimdeki sembol eklenip varsayılan eşlemeyle çekilebilir.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
  - sources/04_oturum_2026-08-13.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-13
---

# symbols

Sembol evreni ve servis eşlemelerinin **tek kaynağı**. `symbols.json`'dan okur:

- `BIST_SYMBOLS` — eklenebilir tüm BIST sembolleri (liste).
- `SPECIALS` — `{SEMBOL: {"yf": yfinance_ticker, "tv": tradingview_sembol}}`
  (XAUUSD, endeks, FX/kripto vb.).
- `KNOWN` — `BIST ∪ SPECIALS`; doğru servis eşlemesi (`tv_symbol`/`yf_ticker`)
  için hâlâ kullanılır.

Amaç: fiyat (yfinance) ve RSI (TradingView) eşlemesinin iki farklı serviste
tutarlı kalması. DeepR bulgusu G52'nin kökü buydu: `XU050` sembol listesinde
vardı ama `data_fetcher` haritalarında yoktu → tek kaynağa toplandı.

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
- [[known_issues]]
<!-- BACKLINKS:END -->
