---
source: codebase inceleme (overlay.py, main.py, data_fetcher.py, config.py, logic.py)
retrieved: 2026-08-06
type: codebase_snapshot
immutable: true
---

# EkranHisse — Proje Özeti (Kaynak Snapshot)

macOS üzerinde çalışan PySide6 tabanlı BIST hisse overlay uygulaması.
Sağ kenarda yarı-şeffaf bir panel olarak açılır; hisse fiyatları, değişim yüzdesi
ve sparkline grafikleri gösterir. TradingView WebSocket üzerinden gerçek zamanlı
fiyat çeker. Twitter/X sekmesi ve not paneli de bulunur.

## Dosya yapısı
- `main.py` — Giriş noktası; tek instance kilidi, Qt signal köprüsü, timer'lar
- `overlay.py` — Ana pencere (OverlayWindow), StockRow, Sparkline (HA), widget'lar
- `data_fetcher.py` — TV WebSocket fiyat + RSI çekici, yfinance fallback
- `config.py` — notes_config.env okuyucu (tek merkez)
- `logic.py` — Yardımcı mantık (tarih, fiyat formatlama vb.)
- `notes_api_client.py` — GitHub Gist not API istemcisi
- `EkranHisse.app` — macOS uygulama paketi; içinde Resources/ ile özdeş

## Önemli sabitler
- Fiyat yenileme: 10 saniye
- RSI yenileme: 5 dakika
- Sparkline MAX: 24 nokta (pseudo Heikin-Ashi)
- TradingView alanları: lp, chp, ch, volume, average_volume
