---
title: Bilinen Sorunlar
type: synthesis
summary: EkranHisse'de DeepR review (11 boyut, adversarial verify) ve canlı çalıştırmayla doğrulanmış açık bug'lar ve teknik borç; öncelikli düzeltme listesi.
sources:
  - sources/01_proje_ozet.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-06
---

# Bilinen Sorunlar

DeepR çok-boyutlu review (2026-08-06, 11 boyut × adversarial doğrulama, 68 doğrulanmış bulgu) ve uygulamayı canlı çalıştırma sonucu ortaya çıkan açık sorunlar. Güvenlik/bağımlılık/ölü-kod maddeleri commit `4bdf973` ile giderildi; aşağıdakiler **hâlâ açık**.

## Kritik / Yüksek (açık)

### RSI zinciri baştan sona ölü
- `overlay.py:2008` `_fetch` içinde `self._signals.rsi_signal.emit(s, rsi)` çağrılıyor ama `_AppSignals` üzerinde **`rsi_signal` tanımlı değil** → RSI thread'i her tetikte `AttributeError` ile düşüyor (**canlı log ile doğrulandı, 2026-08-06**).
- Zincirin ucundaki `StockRow.update_rsi` (`overlay.py:718-719`) zaten yalnızca `pass` — RSI hiçbir yerde gösterilmiyor.
- Sonuç: her 5 dk'da sembol başına TradingView WebSocket açılıp RSI hesaplanıyor, ama tüm iş boşa gidiyor.
- **Düzeltme yönü:** RSI gösterilecekse `_AppSignals`'a `rsi_signal` eklenmeli + `update_rsi` doldurulmalı; gösterilmeyecekse `_rsi_timer`/`_rsi_refresh` tamamen kaldırılmalı. Bkz: [[overlay_window]], [[stock_row]], [[data_fetcher]].

### stocks.json bundle içine yazılamıyor (PermissionError)
- Uygulama `.app` **içindeki** `Contents/Resources/stocks.json`'a yazmaya çalışıyor; macOS `.app` paket içine yazmayı engelliyor → `PermissionError` (**canlı log ile doğrulandı**).
- `save_stocks` ayrıca atomik değil (geçici dosya + `os.replace` yok); yazma sırasında çökme takip listesini sıfırlayabilir.
- **Düzeltme yönü:** kullanıcı verisi (`stocks.json`, `tw_symbols.json`) `~/Library/Application Support/EkranHisse/` gibi yazılabilir bir dizine taşınmalı; yazma atomik yapılmalı.

### Notlar backend'i tutarsız — PHP ölü kod
- `notes_api_client.py` tamamen GitHub Gist API'sine (`api.github.com/gists/{GIST_ID}`) bağlı; repodaki `notes_api.php` + `test.php` (X-Secret token, `notes_data.json`) **hiçbir yerden çağrılmıyor**.
- `NASIL-UYGULANIR.md` hâlâ "notes_api.php entegrasyonu"ndan bahsediyor (yanıltıcı).
- **Düzeltme yönü:** PHP dosyaları silinmeli veya doküman gerçeğe göre güncellenmeli.

## Orta / Düşük (açık)

- **Kırılgan veri katmanı:** fiyat/RSI, TradingView'in yayınlanmamış WS protokolünü tersine mühendislikle + `auth_token`'ı disclaimer HTML'inden regex ile kazıyarak alıyor; protokol/HTML değişince tüm veri katmanı çöker. Bkz: [[data_fetcher]].
- **Ölü kod:** `TargetBar` sınıfı hiç örneklenmiyor (`overlay.py:538-563`); `_fetch_rsi_one` çağrılmıyor (`data_fetcher.py:193-243`); `reorder_started` sinyali hiçbir slota bağlı değil.
- **`XU050`** `_BIST_SYMBOLS`'te var ama `data_fetcher` sembol haritalarında yok → eklenirse veri gelmez.
- **`TWITTER_QUERY`** env'de tanımlı ama okunmuyor; ayrıca `is:retweet` değeri kodun `-is:retweet` davranışının tersini söylüyor (kafa karıştırıcı ölü config).
- **Twitter API** 429 rate-limit için retry/backoff yok; HTTP hataları yutuluyor.
- **Test boşluğu:** `_calc_rsi` (kritik saf hesap) ve tüm WebSocket/ağ akışı test dışı; lint/tip aracı (ruff/mypy) kurulu değil.
- **Doküman kayması:** `NASIL-UYGULANIR.md` geometri/etkileşim değerleri koddan farklı (ör. 320px vs 300, 220ms vs 120ms).

## Kullanıcı aksiyonu (kod dışı)
- **Token rotasyonu:** TradingView `sessionid`, GitHub PAT ve Twitter Bearer geçmişte açık dosyalarda/zip'lerde bulunmuştu — hesap tarafında iptal edip yenilenmeli, sonra `notes_config.env` güncellenmeli. Bkz: [[architecture_overview]] güvenlik notu.

## İlgili
- [[architecture_overview]]
- [[data_fetcher]]
- [[overlay_window]]
- [[stock_row]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
