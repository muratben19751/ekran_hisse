---
title: Mimari Genel Bakış
type: synthesis
summary: EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, uygulama paketi, bağımlılıklar ve env-tabanlı sır yönetimi.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-07
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
- Thread → UI köprüsü: `Signal/Slot` (`_AppSignals` QObject)
- **Auth token:** `_tv_auth_token_lock` ile thread-safe cache; paralel WS başlangıcında N HTTP isteği oluşması engellendi

## Güvenlik ve yapılandırma
Tüm sırlar `~/.ekranhisse/notes_config.env`'de tutulur; yok ise proje dizinindeki `notes_config.env`'e fallback. `config.py` üzerinden tek noktadan okunur: `GIST_ID`, `GITHUB_TOKEN`, `TWITTER_BEARER_TOKEN`, `TV_SESSION_ID`. **Bundle'da credentials tutulmaz** — `EkranHisse.app/Contents/Resources/notes_config.env` kaldırıldı; `setup.command` kurulumda `~/.ekranhisse/` dizinine kopyalar.

## Uygulama paketi senkronizasyonu
`EkranHisse.app/Contents/Resources/` içindeki `.py` dosyaları proje kökündeki kaynaklarla özdeş tutulur. **Tek aktif kaynak proje köküdür.**

## Bağımlılıklar
`requirements.txt` tek kaynaktır: `PySide6`, `yfinance`, `websocket-client`, `requests`, `pyobjc-framework-Cocoa`.

## Bundle launcher
`Contents/MacOS/EkranHisse` → `arch -arm64 /usr/bin/python3 -W ignore main.py` → log: `~/Library/Logs/EkranHisse.log`

## Performans notları (2026-08-07)
- Özel semboller (XAUUSD vb.) tek `yf.download()` çağrısıyla toplu çekilir
- `StockPickerSheet._filter()` `addItems()` batch ile tek repaint
- Bölüm collapse/expand `card.setVisible()` ile yapılır, `_rebuild_rows()` tetiklemez
- `notes_api_client.save_notes()` "latest wins" serialize worker — race condition yok

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
