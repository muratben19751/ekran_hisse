---
title: OverlayWindow
type: entity
summary: Ana pencere widget'ı; şeffaf macOS overlay olarak sağ kenarda açılır, hisse/Twitter/not sekmelerini barındırır.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-06
---

# OverlayWindow

`overlay.py` içindeki ana widget. PySide6 `QWidget` tabanlı, macOS'ta tam yükseklikte
şeffaf bir overlay olarak sağ kenarda konumlanır. Sekme çubuğu (◀) ile açılıp kapanır.

## Sekmeler
- **Hisse (StockPanel)** — BIST hisse takip listesi, fiyat + sparkline
- **Twitter/X** — Takip edilen hesapların tweet akışı
- **Notlar** — GitHub Gist üzerinden senkronlanan not paneli

## Veri akışı
`_AppSignals` nesnesi üzerinden thread-safe signal/slot:
- `data_signal` → `apply_data()` — fiyat sonuçları
- `notes_signal` → `apply_notes()` — not listesi

> **Bilinen sorun (canlı doğrulandı, 2026-08-06):** `_fetch` içinde `_signals.rsi_signal.emit(...)` çağrılıyor (`overlay.py:2008`) ama `_AppSignals` üzerinde **`rsi_signal` tanımlı değil** → RSI thread'i her tetiklendiğinde `AttributeError` ile düşüyor. RSI zinciri baştan sona ölü. Ayrıntı: [[known_issues]].

## Timer'lar
- Fiyat: 10 sn (`QTimer`)
- RSI: 5 dk (`QTimer`), başlangıçta 3 sn gecikme — ancak yukarıdaki nedenle sonuç üretmiyor.

## İlgili
- [[sparkline]]
- [[stock_row]]
- [[data_fetcher]]
- [[architecture_overview]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[known_issues]]
- [[sparkline]]
- [[stock_row]]
<!-- BACKLINKS:END -->
