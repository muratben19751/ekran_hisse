---
title: symbols
type: entity
summary: Sembol evreninin tek kaynağı — symbols.json'dan BIST_SYMBOLS/SPECIALS/KNOWN; fiyat (yfinance) ve RSI (TradingView) ticker eşlemesi tek yerde tutulur.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-12
---

# symbols

Sembol evreni ve servis eşlemelerinin **tek kaynağı**. `symbols.json`'dan okur:

- `BIST_SYMBOLS` — eklenebilir tüm BIST sembolleri (liste).
- `SPECIALS` — `{SEMBOL: {"yf": yfinance_ticker, "tv": tradingview_sembol}}`
  (XAUUSD, endeks, FX/kripto vb.).
- `KNOWN` — `BIST ∪ SPECIALS`; hisse ekleme doğrulaması bu küme üzerinden yapılır
  (`is_known`).

Amaç: fiyat (yfinance) ve RSI (TradingView) eşlemesinin iki farklı serviste
tutarlı kalması. DeepR bulgusu G52'nin kökü buydu: `XU050` sembol listesinde
vardı ama `data_fetcher` haritalarında yoktu → tek kaynağa toplandı.

## İlgili
- [[data_fetcher]]
- [[architecture_overview]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
<!-- BACKLINKS:END -->
