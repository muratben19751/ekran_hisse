---
title: Mimari Genel Bakış
type: synthesis
summary: EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü ve uygulama paketi.
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
`EkranHisse.app/Contents/Resources/` içindeki `.py` dosyaları proje kökündeki kaynaklarla özdeş tutulur. Değişiklik sonrası manuel sync gerekir.

## Bundle launcher
`Contents/MacOS/EkranHisse` → `arch -arm64 /usr/bin/python3 -W ignore main.py` → log: `~/Library/Logs/EkranHisse.log`

## İlgili
- [[overlay_window]]
- [[data_fetcher]]
- [[sparkline]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[overlay_window]]
<!-- BACKLINKS:END -->
