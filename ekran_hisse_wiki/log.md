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
