---
title: OverlayWindow
type: entity
summary: Ana pencere widget'ı; şeffaf macOS overlay olarak sağ kenarda açılır, hisse/Twitter/not sekmelerini barındırır; floating, monitör geçişi ve sürükleme destekler.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
last_updated: 2026-08-11
---

# OverlayWindow

`overlay.py` içindeki ana widget. PySide6 `QWidget` tabanlı, macOS'ta şeffaf bir
overlay olarak sağ kenarda konumlanır. Sekme çubuğu (◧/✎/𝕏) ile açılıp kapanır.

## Sekmeler
- **Hisse (◧)** — BIST hisse takip listesi, fiyat + sparkline + RSI
- **Notlar (✎)** — GitHub Gist üzerinden senkronlanan not paneli
- **Twitter/X (𝕏)** — Takip edilen hesapların tweet akışı

## Başlık satırı kontrolleri (2026-08-11)
Her sayfanın başlık satırında üç buton bulunur:
- **📌** — Panel'i açık tut (`_pinned`); odak kaybında kapanmaz
- **⬆** (mavi=aktif) — Floating/always-on-top toggle; `_toggle_float()` → Qt flag + NSWindow level 1001
- **⊞** — Monitörler arası taşıma; tek monitörde gizli

## Sürükleme (2026-08-11)
Başlık satırı widget'ına `mousePressEvent/Move/Release` bağlı; pencere serbestçe taşınabilir.
Taşıma sırasında `self._current_sc` güncellenir.

## Floating / Always-on-Top (2026-08-11)
- `self._floating = True` varsayılan
- Floating açıkken: `_toggle`, `changeEvent`, `eventFilter`, global mouse monitor — hepsi panel'i kapatmaz
- `keep_top` QTimer (15 sn): `window._floating and _set_window_level(window)`

## Monitör yönetimi (2026-08-11)
- `self._current_sc` — aktif ekranın geometrisi; animasyon closure ve NSEvent koordinat dönüşümü kullanır
- `_cycle_monitor()` → `QApplication.screens()` döngüsü → `_reposition_to_screen(screen)`
- `_COLLECTION_BEHAVIOR` modül düzeyinde tek sabit (DRY; `_NSScreen` import'u kaldırıldı)

## Veri akışı
`_AppSignals` nesnesi üzerinden thread-safe signal/slot:
- `data_signal` → `apply_data()` — fiyat sonuçları (`try/finally` ile `_fetching` her durumda temizlenir)
- `notes_signal(object)` → `apply_notes()` — `None` hata sinyali olarak taşınır; "Bağlantı hatası" gösterilir
- `rsi_signal` → `apply_rsi()` — RSI sonuçları (5/15/30/60 dk)

## Timer'lar
- Fiyat: 60 sn (`REFRESH_INTERVAL_MS`)
- RSI: 5 dk, başlangıçta 3 sn gecikme
- Twitter poll: 60 sn
- Outside-click fallback: 150 ms (global monitor aktifse durur)

## Önemli fixler

### 2026-08-11
- `update_rsi`: `or` zinciri → `next(...is not None)` — NoneType/falsy-zero TypeError giderildi
- `fetch_notes None→[]` lambda kaldırıldı; `apply_notes(None)` çalışıyor
- `_fetching` `try/finally` ile güvenceye alındı
- `StockPickerSheet._ok()` `_BIST_SYMBOLS` kontrolü eklendi
- `YKBK` → `YKBNK` düzeltildi
- `main.py` lock dosyası `try/except OSError` ile güvenceye alındı

### 2026-08-07
- `prev == 0` guard kaldırıldı; her sekme geçişinde veri yenileniyor
- `_tw_loading` flag guard — çoklu thread spawn engellendi
- Not kayıt callback `ok` parametresi kontrolü
- `tempfile + os.replace` atomic write
- `card.setVisible()` — collapse artık `_rebuild_rows()` tetiklemiyor
- `_set_ns_window_level` tek canonical fonksiyon

## İlgili
- [[sparkline]]
- [[stock_row]]
- [[data_fetcher]]
- [[architecture_overview]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[known_issues]]
- [[sparkline]]
- [[stock_row]]
<!-- BACKLINKS:END -->
