---
title: Bilinen Sorunlar
type: synthesis
summary: EkranHisse'de DeepR review ve canlı doğrulamayla tespit edilen açık bug'lar ve teknik borç; 2026-08-11 itibarıyla çözülen maddeler işaretli.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-11
---

# Bilinen Sorunlar

İki ayrı DeepR review turu (2026-08-06 ve 2026-08-11) ile ortaya çıkan sorunlar. Commit `b802327` (2026-08-07) ilk turu, bu oturum (2026-08-11) ikinci turu kapatmıştır.

---

## ✅ Giderilen (2026-08-07, commit b802327)

| # | Sorun | Düzeltme |
|---|-------|----------|
| G1 | RSI zinciri ölü | `rsi_signal` tanımlı; `update_rsi()` aktif |
| G2 | `price=0.0` eksik veri sayılıyordu | `lp if lp is not None else last_price` |
| G3 | Not kayıt hatası "Kaydedildi" gösteriyordu | Callback `ok` parametresine göre hata mesajı |
| G4 | `save_notes` race condition | "Latest wins" serialize worker |
| G5 | `save_stocks` sessiz hata | Atomic write + `warnings.warn` |
| G6 | Auth token race condition | `_tv_auth_token_lock` |
| G7 | Twitter çoklu thread spawn | `_tw_loading` flag guard |
| G8 | Kısmi sembol ekleme | `_BIST_SYMBOLS` kontrolü |
| G9 | Boş bölüm adı kabul ediliyordu | `TextSheet._ok` guard |
| G10 | `entry=0` PnL hesaplanmıyordu | `is not None and != 0` |
| G11 | Sekme geçişinde notlar yenilenmiyordu | `prev != mode` koşulu |
| G12 | Credentials bundle'da düz metin | `~/.ekranhisse/notes_config.env`'e taşındı |
| G13 | `notes_api.php` secret hardcode | `getenv('EKRANHISSE_SECRET')` |
| G14 | `_fetch_rsi_one` ölü kod | Silindi |
| G15 | `reorder_started` sinyali bağsız | `_on_reorder_started` slot'una bağlandı |
| G16 | `_boost_level` duplikasyonu | `_set_ns_window_level` tek fonksiyon |
| G17 | `_SEP_SYMBOL` duplikasyonu | `logic.py`'dan import |
| G18 | yfinance N thread | Tek `yf.download()` thread |
| G19 | Collapse her seferinde `_rebuild_rows` | `card.setVisible()` ile optimize edildi |

---

## ✅ Giderilen (2026-08-11, bu oturum)

| # | Sorun | Düzeltme |
|---|-------|----------|
| G20 | `update_rsi` NoneType/falsy-zero TypeError | `next(...is not None)` ile güvenli anchor |
| G21 | `fetch_notes None→[]` — "Bağlantı hatası" ölü kod | Lambda kaldırıldı; `apply_notes(None)` çalışıyor |
| G22 | `price=0.0` falsy-zero (data_fetcher) | `lp if lp is not None else last_price` + `is not None` |
| G23 | `_fetching` exception'da temizlenmiyordu | `try/finally` ile her durumda `False` |
| G24 | `_NSScreen` gereksiz import; _COLLECTION_BEHAVIOR 3× tekrar | Modül düzeyinde tek sabit |
| G25 | `GIST_ID` boşken geçersiz URL sessizce oluşuyordu | `_gist_api()` lazy + `ValueError` |
| G26 | `StockPickerSheet._ok()` BIST kontrolü atlıyordu | `_BIST_SYMBOLS` kontrolü eklendi |
| G27 | `_calc_rsi` flat hisse → yanıltıcı `RSI=100.0` | `avg_gain==avg_loss==0` → `None` |
| G28 | `_run_specials_bulk` dead code + NaN/ZeroDivision | `sym_by_ticker` silindi; `math.isnan` koruması |
| G29 | `compute_unread active` parametresi kullanılmıyordu | `if active: return set(), next_seen` |
| G30 | `YKBK` yanlış sembol | `YKBNK` düzeltildi |
| G31 | `datetime` 3 yerel import | Modül düzeyine taşındı |
| G32 | `main.py` lock açılışı try/except dışında | `try/except OSError` ile güvenceye alındı |
| G33 | Eski geliştirme notu docstring | Temizlendi |

---

## ✅ Yeni özellikler (2026-08-11)

| # | Özellik |
|---|---------|
| F1 | `⬆` floating/always-on-top toggle — başlık satırında `📌` yanında; mavi=aktif |
| F2 | `⊞` monitörler arası taşıma butonu — tek monitörde gizli, çok monitörde döngüsel |
| F3 | Başlık satırından sürükleyerek pencereyi serbestçe konumlandırma |
| F4 | Floating açıkken dışarı tıklamada panel kapanmaz (`_toggle`, `changeEvent`, `eventFilter`, global monitor hepsi korumalı) |
| F5 | `_current_sc` ile animasyon closure monitör-aware; taşıma sonrası sağ kenara yapışma korunuyor |

---

## Kritik / Yüksek (hâlâ açık)

### stocks.json konumu
- Bundle içindeki `Contents/Resources/stocks.json`'a yazılıyor; doğru çözüm `~/Library/Application Support/EkranHisse/`.

### Notlar backend'i tutarsız — PHP ölü kod
- `notes_api.php` hiçbir yerden çağrılmıyor; `NASIL-UYGULANIR.md` yanıltıcı.

---

## Orta / Düşük (açık)

- **`_twitter_render`** her çağrıda tüm widget'ları yıkıp yeniden kuruyor — filtre değişiminde show/hide yeterli.
- **`_rebuild_rows`** her mutasyonda tam rebuild — 50 hissede her etkileşimde 50 widget yeniden oluşturuluyor.
- **`TargetBar`** sınıfı hiç örneklenmiyor — ölü kod.
- **Twitter sembol sayısı** limitsiz; ~40+ sembolde 512 byte Twitter API limitini aşıyor.
- **Twitter API 429** için retry/backoff yok.
- **`TWITTER_QUERY`** env'de tanımlı ama okunmuyor — dead config.
- **`XU050`** `_BIST_SYMBOLS`'te var ama `data_fetcher` haritalarında yok.
- **Lint/tip aracı** (ruff/mypy) kurulu değil.
- **E2E test** hiç yok — `OverlayWindow` hiç örneklenmiyor.
- **TV auth token** sonsuz cache; oturum süresi dolunca yenileme yok.
- **Not editörü** karakter limiti yok; GitHub Gist 10 MB sınırı.
- **Bölüm adında `:` karakteri** sembol ayrıştırmasını bozuyor.

---

## Kullanıcı aksiyonu (kod dışı)
- **Token rotasyonu:** TradingView `sessionid`, GitHub PAT ve Twitter Bearer geçmişte bundle içinde açık bulunmuştu → hesap tarafında iptal + yenile, `~/.ekranhisse/notes_config.env` güncelle.

## İlgili
- [[architecture_overview]]
- [[data_fetcher]]
- [[overlay_window]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[overlay_window]]
<!-- BACKLINKS:END -->
