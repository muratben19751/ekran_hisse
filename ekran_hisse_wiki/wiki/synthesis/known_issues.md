---
title: Bilinen Sorunlar
type: synthesis
summary: EkranHisse'de DeepR review ve canlı doğrulamayla tespit edilen açık bug'lar ve teknik borç; 2026-08-07 itibarıyla çözülen maddeler işaretli.
sources:
  - sources/01_proje_ozet.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-07
---

# Bilinen Sorunlar

DeepR çok-boyutlu review (2026-08-06, 11 boyut × adversarial doğrulama, 61 hayatta kalan bulgu) ve uygulamayı canlı çalıştırma sonucu ortaya çıkan sorunlar. Commit `b802327` (2026-08-07) kapsamlı düzeltme turunu içeriyor; aşağıdakiler hâlâ **açık**.

---

## ✅ Giderilen (2026-08-07, commit b802327)

| # | Sorun | Düzeltme |
|---|-------|----------|
| G1 | RSI zinciri ölü (`update_rsi = pass`, `rsi_signal` tanımsız) | `rsi_signal` artık `_AppSignals`'ta tanımlı; `update_rsi()` RSI etiketlerini gösteriyor |
| G2 | `price=0.0` eksik veri sayılıyordu (`or` operatörü) | `lp if lp is not None else last_price` |
| G3 | Not kayıt hatası "Kaydedildi" gösteriyordu | Callback `ok` parametresine göre hata mesajı |
| G4 | `save_notes` eş zamanlı race condition | "Latest wins" serialize worker |
| G5 | `save_stocks` sessiz hata (PermissionError yutuluyordu) | Atomic write + `warnings.warn` |
| G6 | Auth token race condition (lock yok) | `_tv_auth_token_lock = threading.Lock()` |
| G7 | Twitter çoklu thread spawn | `_tw_loading` flag guard |
| G8 | Kısmi sembol ekleme (geçersiz) | `_BIST_SYMBOLS` kontrolü |
| G9 | Boş bölüm adı kabul ediliyordu | `TextSheet._ok` guard |
| G10 | `entry=0` PnL hesaplanmıyordu | `is not None and != 0` |
| G11 | Sekme geçişinde notlar yenilenmiyordu | `prev != mode` koşulu |
| G12 | Credentials bundle içinde düz metin | `~/.ekranhisse/notes_config.env`'e taşındı |
| G13 | `notes_api.php` secret hardcode | `getenv('EKRANHISSE_SECRET')` |
| G14 | `_fetch_rsi_one` ölü kod | Silindi |
| G15 | `reorder_started` sinyali bağsız | `_on_reorder_started` slot'una bağlandı |
| G16 | `_boost_level` duplikasyonu | `_set_ns_window_level` tek fonksiyon |
| G17 | `_SEP_SYMBOL` duplikasyonu | `logic.py`'dan import |
| G18 | yfinance N thread | Tek `yf.download()` thread |
| G19 | Collapse her seferinde `_rebuild_rows` | `card.setVisible()` ile optimize edildi |

---

## Kritik / Yüksek (hâlâ açık)

### stocks.json konumu
- Uygulama `.app` **bundle içindeki** `Contents/Resources/stocks.json`'a yazmaya çalışıyor; `save_stocks` artık atomik ve uyarı veriyor ama **doğru çözüm** kullanıcı verisini `~/Library/Application Support/EkranHisse/` gibi yazılabilir dizine taşımak.

### Notlar backend'i tutarsız — PHP ölü kod
- `notes_api_client.py` tamamen GitHub Gist API'sine bağlı; `notes_api.php` hiçbir yerden çağrılmıyor (dosyaya "kullanılmıyor" notu eklendi ama silinmedi).
- `NASIL-UYGULANIR.md` hâlâ "notes_api.php entegrasyonu"ndan bahsediyor (yanıltıcı).

---

## Orta / Düşük (açık)

- **Kırılgan veri katmanı:** TradingView'in yayınlanmamış WS protokolü + `auth_token` HTML regex ile kazınıyor; protokol değişince tüm veri katmanı çöker. Bkz: [[data_fetcher]].
- **`TargetBar` sınıfı** hiç örneklenmiyor (`overlay.py`) — ölü kod.
- **`XU050`** `_BIST_SYMBOLS`'te var ama `data_fetcher` haritalarında yok → veri gelmez.
- **`TWITTER_QUERY`** env'de tanımlı ama okunmuyor; `is:retweet` değeri kodun `-is:retweet` davranışının tersini söylüyor.
- **Twitter API** 429 rate-limit için retry/backoff yok.
- **Lint/tip aracı** (ruff/mypy) kurulu değil.
- **Doküman kayması:** `NASIL-UYGULANIR.md` geometri değerleri koddan farklı.

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
<!-- BACKLINKS:END -->
