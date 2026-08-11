---
title: Mimari Genel Bakış
type: synthesis
summary: EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, floating/monitör yönetimi, uygulama paketi ve env-tabanlı sır yönetimi.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
last_updated: 2026-08-11
---

# Mimari Genel Bakış

## Katmanlar

```
┌─────────────────────────────────┐
│  EkranHisse.app (macOS bundle)  │
│  └── Contents/Resources/        │
│       ├── main.py  ←── giriş   │
│       ├── overlay.py  ←── UI   │
│       └── data_fetcher.py ←── veri │
└─────────────────────────────────┘
```

## Veri akışı

```
TradingView WebSocket
  └─→ fetch_tv_prices() / fetch_tv_rsi()
        └─→ _AppSignals (thread-safe)
              └─→ OverlayWindow.apply_data() / apply_rsi()
                    └─→ StockRow.update_data() / update_rsi()
                          └─→ Sparkline.push() → paintEvent()
                          └─→ lbl_rsi (5m/15m/30m/60m etiketleri)
```

## Thread modeli
- Ana thread: Qt event loop
- Arka plan thread'leri: TV WebSocket (daemon), RSI fetch (Semaphore(4)), not fetch (serialize worker)
- Thread → UI köprüsü: `Signal/Slot` (`_AppSignals` QObject; `notes_signal = Signal(object)` — `None` taşıyabilir)
- **Auth token:** `_tv_auth_token_lock` ile thread-safe cache

## Pencere yönetimi (2026-08-11)

### Floating / Always-on-Top
- `self._floating = True` varsayılan — uygulama her zaman üstte başlar
- `⬆` butonu (başlık satırı): `_toggle_float()` → Qt `WindowStaysOnTopHint` flag + NSWindow level 1001
- `keep_top` QTimer (15 sn): `window._floating and _set_window_level(window)` — kapalıyken çalışmaz
- Floating açıkken `_toggle`, `changeEvent`, `eventFilter`, global mouse monitor hepsi panel'i kapatmaz

### Monitörler arası taşıma
- `⊞` butonu: `_cycle_monitor()` → `QApplication.screens()` döngüsü → `_reposition_to_screen()`
- Tek monitörde buton gizli (`setVisible(len(screens) > 1)`)
- `self._current_sc` instance değişkeni — animasyon closure ve NSEvent koordinat dönüşümü bunu kullanır

### Sürükleme
- Başlık satırı (`_head_row` widget'ı) `mousePressEvent/Move/Release` ile pencereyi serbestçe taşır
- Taşıma sırasında `self._current_sc = self.screen().geometry()` güncellenir

### _COLLECTION_BEHAVIOR sabiti
- `overlay.py` modül düzeyinde tek kez tanımlı: `_CB_ALL_SPACES | _CB_STATIONARY`
- `main.py`, `_apply_float`, `_reposition_to_screen` hepsi bu sabiti kullanır (DRY)

## Güvenlik ve yapılandırma
Tüm sırlar `~/.ekranhisse/notes_config.env`'de tutulur; yok ise proje dizinindeki `notes_config.env`'e fallback. `config.py` üzerinden tek noktadan okunur: `GIST_ID`, `GITHUB_TOKEN`, `TWITTER_BEARER_TOKEN`, `TV_SESSION_ID`. **Bundle'da credentials tutulmaz.**

`GIST_ID` boşsa `notes_api_client._gist_api()` anında `ValueError` fırlatır — sessiz geçersiz URL üretilmez.

## Uygulama paketi senkronizasyonu
`EkranHisse.app/Contents/Resources/` içindeki `.py` dosyaları proje kökündeki kaynaklarla özdeş tutulur. **Tek aktif kaynak proje köküdür.**

## Bağımlılıklar
`requirements.txt` tek kaynaktır: `PySide6`, `yfinance`, `websocket-client`, `requests`, `pyobjc-framework-Cocoa`.

## Bundle launcher
`Contents/MacOS/EkranHisse` → `arch -arm64 /usr/bin/python3 -W ignore main.py` → log: `~/Library/Logs/EkranHisse.log`

## Performans notları
- Özel semboller (XAUUSD vb.) tek `yf.download()` çağrısıyla toplu çekilir; NaN/ZeroDivision koruması var
- `StockPickerSheet._filter()` `addItems()` batch ile tek repaint
- Bölüm collapse/expand `card.setVisible()` ile yapılır, `_rebuild_rows()` tetiklemez
- `notes_api_client.save_notes()` "latest wins" serialize worker — race condition yok
- `_fetching` bayrağı `try/finally` ile her durumda temizlenir — exception'da veri dondurması önlendi

## İlgili
- [[overlay_window]]
- [[data_fetcher]]
- [[sparkline]]
- [[stock_row]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[known_issues]]
- [[overlay_window]]
<!-- BACKLINKS:END -->
