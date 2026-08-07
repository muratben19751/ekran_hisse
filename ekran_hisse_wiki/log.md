# ekran_hisse Wiki İşlem Günlüğü (append-only)

Çelişkiler, yeni boşluklar ve senkron notları buraya eklenir.

## 2026-08-06 — İlk senkron
- Wiki bootstrap ile kuruldu (ekran_hisse_wiki/)
- 5 sayfa oluşturuldu: overlay_window, sparkline, stock_row, data_fetcher, architecture_overview
- Sparkline pseudo Heikin-Ashi → çizgi grafik geçişi dokümante edildi
- Lint: 0 broken_links, 0 orphans, 0 stubs

## 2026-08-06 — DeepR review sonrası güvenlik/temizlik senkronu
- **Güvenlik:** TradingView `sessionid` çerezi `data_fetcher.py`'den çıkarılıp `config.TV_SESSION_ID` üzerinden git-izlenmeyen `notes_config.env`'e taşındı; boşsa `unauthorized_user_token` fallback. Kök + `.app` bundle senkronlandı.
- **Bağımlılıklar:** `requirements.txt`'e eksik olan `websocket-client`, `requests`, `pyobjc-framework-Cocoa` eklendi (temiz makinede ImportError çöküşü düzeltildi). `install.sh`/`setup.command` artık `pip install -r requirements.txt` çağırıyor.
- **Ölü kod temizliği:** ~7300 satır kaldırıldı — 4 yedek dosya (`overlay 2.py`, `overlay_1b_yedek.py`, `overlay_eski.py`, `overlay_inceleme_oncesi_yedek.py`) ve eski 3. kopya `uygulama/` dizini (`git rm`). `.gitignore` sadeleştirildi.
- Güncellenen wiki sayfaları: [[data_fetcher]] (TV Auth + Bağımlılıklar), [[architecture_overview]] (Bağımlılıklar + Güvenlik/yapılandırma + senkron notu).
- Lint: 0 broken_links, 0 orphans, 0 stubs (temiz).
- **Açık boşluk (kullanıcı aksiyonu):** token rotasyonu (TV `sessionid`, GitHub PAT, Twitter Bearer) hesap tarafında yapılmalı — bkz. DeepR raporu. RSI zinciri ölü (`StockRow.update_rsi = pass`) ve PHP `notes_api.php` backend'i kullanılmıyor; ileride ele alınacak.

## 2026-08-07 — DeepR kapsamlı düzeltme turu + wiki senkronu

- **Commit b802327:** 19 bulgu giderildi (güvenlik, sessiz hatalar, ölü kod, performans, RSI).
- **Güncellenen wiki sayfaları (5):** [[data_fetcher]], [[stock_row]], [[overlay_window]], [[architecture_overview]], [[known_issues]].
- **data_fetcher:** auth token lock, yfinance bulk fetch, `price=0.0` fix, `_fetch_rsi_one` silindi, interval validation.
- **stock_row:** `update_rsi()` implement edildi — `5m/15m/30m/60m` RSI etiketleri, renk kodlu; layout 80px RSI alanı eklendi.
- **overlay_window:** sekme geçişi guard, Twitter thread guard, not hata mesajı, `save_stocks` atomic, collapse optimize, `_set_ns_window_level` tek fonksiyon.
- **architecture_overview:** güvenlik (`~/.ekranhisse/`), performans notları, veri akışı RSI ile güncellendi.
- **known_issues:** giderilen 19 madde tablo olarak işaretlendi; açık kalan sorunlar (stocks.json konumu, PHP ölü kod, kırılgan TV protokolü) korundu.
- Backlinks 6 sayfada tazelendi; index yenilendi. Lint: 0/0/0/0/0/0 (temiz).

- Uygulama restart edildi; canlı log iki önceden-var-olan bug'ı DOĞRULADI: (1) `_AppSignals.rsi_signal` tanımsız → RSI thread'i AttributeError ile düşüyor (RSI zinciri baştan sona ölü), (2) `.app` bundle içindeki `stocks.json`'a yazma PermissionError.
- **Düzeltme (wiki gerçeği):** [[overlay_window]] "Veri akışı" bölümü yanlış `rsi_signal → apply_rsi()` iddiasını içeriyordu; gerçeğe (ölü/bug) göre düzeltildi. [[stock_row]]'a boş `update_rsi` notu eklendi.
- **Yeni sayfa:** [[known_issues]] (synthesis) — DeepR'ın 68 doğrulanmış bulgusundan + canlı çalıştırmadan derlenen açık bug'lar ve teknik borç; öncelik sırasıyla. [[architecture_overview]]'a çift yönlü bağlandı.
- backlinks 6 sayfada tazelendi; index yenilendi. Lint: 0/0/0/0/0/0 (temiz).
