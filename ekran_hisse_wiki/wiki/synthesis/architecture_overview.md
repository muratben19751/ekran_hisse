---
title: Mimari Genel Bakış
type: synthesis
summary: EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, paths/symbols/twitter_client/applog modülleri, floating/monitör yönetimi ve Keychain-öncelikli sır yönetimi.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
  - sources/03_deepr_review_round2_2026-08-12.md
last_updated: 2026-08-13
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
- Arka plan thread'leri: TV WebSocket (daemon, `ping_interval`/`ping_timeout` + `setdefaulttimeout`), RSI fetch, not fetch (serialize worker), Twitter poll
- Thread → UI köprüsü: `Signal/Slot` (`_AppSignals` QObject; `notes_signal = Signal(object)` — `None` taşıyabilir)
- **Durum yalnız ana thread'de değişir.** Worker'lar sonucu Signal ile geçirir:
  `data_signal`, `notes_signal`, `rsi_signal`, ve OverlayWindow-yerel `tw_poll_error`,
  `rsi_done`. Örn. RSI worker biterken `rsi_done.emit()` (bir `try/finally` içinde) →
  `_on_rsi_done` ana thread'de `_rsi_fetching=False` yapar (cross-thread yazım yok).
- **Auth token:** `_tv_auth_token_lock` ile thread-safe cache; başarısız denemede
  negatif TTL cache (60 sn) tekrarlı HTTP'yi önler.

## Modül haritası
| Modül | Rol |
|-------|-----|
| `main.py` | Giriş; `paths.ensure_data_dir()`, `fcntl` tek-instance kilidi, Qt app + Signal kablaj |
| `overlay.py` | Tüm UI: `OverlayWindow`, `StockRow`, `Sparkline`, sheet'ler, floating/monitör |
| `data_fetcher.py` | TV WebSocket fiyat/RSI + yfinance özel semboller; NaN/timeout korumalı |
| [[paths]] | `~/.ekranhisse` yol politikası tek kaynak (`DATA_DIR`/`ensure_data_dir`/`data_file`) |
| [[symbols]] | Sembol evreni tek kaynak (`symbols.json` → BIST ∪ SPECIALS = KNOWN; yf & tv eşlemesi) |
| [[twitter_client]] | 𝕏 ağ katmanı (UI'dan ayrık; Nitter search RSS köprüsü — bearer'sız, çoklu instance fallback + 429 backoff) |
| `notes_api_client.py` | GitHub Gist not senkronu (last-write-wins) |
| `config.py` | Sır okuma: Keychain-öncelikli, `.env` geçiş fallback |
| `applog.py` | Merkezî logger (konsol + `~/Library/Logs/EkranHisse.log`) |

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
Sırlar `config.py` üzerinden tek noktadan okunur: `GIST_ID`, `GITHUB_TOKEN`,
`TWITTER_BEARER_TOKEN`, `TV_SESSION_ID`. Okuma sırası: **önce macOS Keychain**
(`_keychain_get`, `security` CLI), yoksa `~/.ekranhisse/notes_config.env` düz-metin
**geçiş** fallback'i (bulunursa bir kez güvenlik uyarısı verilir). **Bundle'da
credentials tutulmaz.** Sabitler import anında bir kez okunur (snapshot); uygulama
açıkken eklenen sır süreç yeniden başlatılana dek görülmez.

`GIST_ID` boşsa `notes_api_client._gist_api()` anında `ValueError` fırlatır — sessiz
geçersiz URL üretilmez.

`config.NITTER_INSTANCES` (2026-08-13) sır DEĞİL — public Nitter URL listesi (virgülle
çoklu); boşsa [[twitter_client]] kod içi varsayılan listesini kullanır. Keychain/env'den
okunabilir ama zorunlu değil.

## Kalıcılık ve yol politikası
Tüm kalıcı veri (`stocks.json`, `tw_symbols.json`, `notes_config.env`, `.ekranhisse.lock`)
`~/.ekranhisse` altında; yol politikası [[paths]] modülünde tek kaynak. `stocks.json`
artık bundle Resources'a YAZILMAZ (kullanıcı verisi; `.gitignore`'da). Atomik JSON
yazımı: tmp dosyaya yaz + `os.replace` (yazma hatasında mevcut dosya bozulmaz).

`stocks.json` kaydı `{"symbol", "entry", "exit", "qty"}` (2026-08-13'te `qty`/adet
eklendi — [[stock_row]] K/Z tutar hesabı için); `entry`/`exit`/`qty` opsiyonel.
`logic.sanitize_stocks` dıştan gelen kaydı güvenli hale getirir (sayı değilse `None`,
`symbol` yoksa satır düşer) — kullanıcı verisi asla silinmez.

**UI tercihleri (2026-08-13):** aynı dizinde iki kalıcı UI dosyası daha:
`ui_scale.json` (font ölçeği `_FONT_SCALE`) ve `ui_geom.json` (panel genişliği +
pencere yüksekliği). İkisi de aynı `load_*`/`save_*` + atomik `_save_json` desenini
kullanır; kullanıcı verisi değil UI durumu olduğundan silinmeleri portföyü/notları
etkilemez. Bkz. [[overlay_window]].

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
- [[paths]]
- [[symbols]]
- [[twitter_client]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[known_issues]]
- [[overlay_window]]
- [[paths]]
- [[symbols]]
- [[twitter_client]]
<!-- BACKLINKS:END -->
