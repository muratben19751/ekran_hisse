---
title: Mimari Genel Bakış
type: synthesis
summary: EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, uygulama paketi, bağımlılıklar ve env-tabanlı sır yönetimi.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-06
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
                    └─→ StockRow.update_data()
                          └─→ Sparkline.push() → paintEvent()
```

## Thread modeli
- Ana thread: Qt event loop
- Arka plan thread'leri: TV WebSocket (daemon), RSI fetch (Semaphore(4)), not fetch
- Thread → UI köprüsü: `Signal/Slot` (`_AppSignals` QObject)

## Uygulama paketi senkronizasyonu
`EkranHisse.app/Contents/Resources/` içindeki `.py` dosyaları proje kökündeki kaynaklarla özdeş tutulur. Değişiklik sonrası manuel sync gerekir (kök → bundle). **Tek aktif kaynak proje köküdür**; eski `uygulama/` kopyası ve `overlay_*_yedek.py`/`overlay_eski.py`/`overlay 2.py` yedekleri (~7300 satır ölü kod) kaldırıldı — bundan sonra yalnızca kök + bundle senkronu takip edilir.

## Bağımlılıklar
`requirements.txt` tek kaynaktır: `PySide6`, `yfinance`, `websocket-client`, `requests`, `pyobjc-framework-Cocoa`. `websocket-client`+`requests` veri katmanının (bkz. [[data_fetcher]]), `pyobjc` ise macOS pencere davranışının zorunlu bağımlılıklarıdır. `install.sh` ve `setup.command` artık elle paket listesi yerine `pip install -r requirements.txt` çağırır.

## Güvenlik ve yapılandırma
Tüm sırlar git-izlenmeyen `notes_config.env`'de tutulur ve `config.py` üzerinden tek noktadan okunur: `GIST_ID`, `GITHUB_TOKEN`, `TWITTER_BEARER_TOKEN`, `TV_SESSION_ID`. TradingView `sessionid` çerezi koddan çıkarılıp env'e taşındı (daha önce `data_fetcher.py`'de hardcoded'dı). `.app` bundle'ı da kendi `notes_config.env` kopyasını taşır.

## Bundle launcher
`Contents/MacOS/EkranHisse` → `arch -arm64 /usr/bin/python3 -W ignore main.py` → log: `~/Library/Logs/EkranHisse.log`

## İlgili
- [[overlay_window]]
- [[data_fetcher]]
- [[sparkline]]
- [[stock_row]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[data_fetcher]]
- [[known_issues]]
- [[overlay_window]]
<!-- BACKLINKS:END -->
