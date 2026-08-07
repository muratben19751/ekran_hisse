---
title: OverlayWindow
type: entity
summary: Ana pencere widget'ı; şeffaf macOS overlay olarak sağ kenarda açılır, hisse/Twitter/not sekmelerini barındırır.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-07
---

# OverlayWindow

`overlay.py` içindeki ana widget. PySide6 `QWidget` tabanlı, macOS'ta tam yükseklikte
şeffaf bir overlay olarak sağ kenarda konumlanır. Sekme çubuğu (◀) ile açılıp kapanır.

## Sekmeler
- **Hisse (StockPanel)** — BIST hisse takip listesi, fiyat + sparkline + RSI
- **Twitter/X** — Takip edilen hesapların tweet akışı
- **Notlar** — GitHub Gist üzerinden senkronlanan not paneli

## Veri akışı
`_AppSignals` nesnesi üzerinden thread-safe signal/slot:
- `data_signal` → `apply_data()` — fiyat sonuçları
- `notes_signal` → `apply_notes()` — not listesi
- `rsi_signal` → `apply_rsi()` — RSI sonuçları (5/15/30/60 dk)

## Timer'lar
- Fiyat: 10 sn (`QTimer`)
- RSI: 5 dk (`QTimer`), başlangıçta 3 sn gecikme

## Sekme geçişi
**Fix (2026-08-07):** `prev == 0` guard kaldırıldı; sekmeler arası her geçişte (`prev != mode`) ilgili veri yenileniyor. Eski davranışta notlar yalnızca kapanmış panelden açılırken yükleniyordu.

## Twitter guard
**Fix (2026-08-07):** `_twitter_load()` çoklu thread spawn engeli eklendi (`_tw_loading` flag). Hızlı sekme değişimi artık paralel HTTP isteği açmıyor.

## Not kayıt geri bildirimi
**Fix (2026-08-07):** `_notes_save_now` callback'i `ok` parametresini kontrol ediyor; hata durumunda "Kaydetme hatası!" gösteriyor (eskiden her zaman "Kaydedildi" yazıyordu).

## save_stocks
**Fix (2026-08-07):** `tempfile + os.replace` ile atomic write; izin hatası artık tek seferlik `warnings.warn` ile raporlanıyor (sessiz yutulmuyor).

## Bölüm collapse
**Performans (2026-08-07):** `_on_collapse_toggled` artık `_rebuild_rows()` yerine doğrudan `card.setVisible()` çağırıyor; `self.cards` dict'i `_rebuild_rows` tarafından tutuluyor.

## macOS pencere seviyesi
`_boost_level` → `_set_ns_window_level(win, level, collection_behavior, make_key)` olarak yeniden adlandırıldı ve `main.py`'deki kopya kaldırıldı; tek canonical fonksiyon.

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
