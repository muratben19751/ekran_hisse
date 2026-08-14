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

## 2026-08-11 — DeepR fix turu + yeni özellikler senkronu

**Güncellenen sayfalar:** `known_issues.md`, `architecture_overview.md`, `overlay_window.md`, `data_fetcher.md`
**Yeni kaynak:** `sources/02_deepr_review_2026-08-11.md`

**Özet:**
- 13 kritik/yüksek fix (G20–G32): falsy-zero, None→[], _fetching try/finally, DRY sabit, GIST_ID lazy, BIST doğrulama, flat RSI, NaN koruması, compute_unread active, YKBNK, datetime modül seviye, lock try/except, docstring
- 5 yeni özellik (F1–F5): floating toggle, monitör geçişi, sürükleme, floating=açıkken kapanmama, _current_sc monitör-aware

**Lint:** 0 broken_links, 0 orphans, 0 missing_summary, 0 stubs

## 2026-08-12 — DeepR 3. tur senkronu — 22 fix + adversarial doğrulama

**Yeni kaynak:** `sources/03_deepr_review_round2_2026-08-12.md` (immutable ham kayıt)
**Güncellenen:** `known_issues.md`, `architecture_overview.md`
**Yeni entity:** `paths`, `symbols`, `twitter_client` (içerikle dolu)

**Özet:**
- known_issues: G34–G55 "Giderilen (3. tur, commit e54430b)" eklendi; stocks.json +
  ölü PHP backend "Kritik/Yüksek açık"tan düştü; _twitter_render filtre-rebuild, XU050,
  ruff yokluğu, E2E test boşluğu, Twitter 429 retry kapandı.
- architecture_overview: sır okuma Keychain-öncelikli + `.env` geçiş fallback gerçeğe
  çekildi; paths/symbols/twitter_client/applog modül haritası; thread modeli
  rsi_done/tw_poll_error + WS ping/timeout + auth negatif cache.
- Bilinçli kapsam: `save_notes` çok-cihaz not-ezme yalnız belgelendi (merge kapsam dışı).

**Doğrulama:** 22 fix adversarial `unfixed_count: 0`; ek tur RSI try/finally + ölen 6
bulgu 6/6 CONFIRMED. Test 191→200, ruff/pyflakes temiz.

**Lint (sonrası):** backlinks 9 sayfa + index yenilendi; broken_links/orphans/
missing_summary/stubs = 0.

---

## 2026-08-13 — Resize özelliği senkronu + Tweet alarm 402 teşhisi

**Kaynak:** `sources/04_oturum_2026-08-13.md` (canlı X API probe + oturum işleri).

**Kod (bu oturum, `overlay.py` + test):**
- Yatay/dikey kenar-köşe boyutlandırma + `ui_geom.json` kalıcılığı; `PANEL_W`/`ekran//2`
  sabitleri → çalışma zamanı `self._panel_w`/`self._win_h`. 211 test (10 yeni), veri korundu.
- (Önceki oturum) font ölçekleme A−/A+ + `ui_scale.json`; sembol evreni `is_known`
  kısıtı kaldırıldı (biçim kontrolü + varsayılan eşleme).

**Wiki güncellemeleri:**
- overlay_window: kenar/köşe boyutlandırma + font ölçekleme bölümleri; sağ→sağ-alt
  yaslama düzeltmesi; 2026-08-13 fix girdisi.
- twitter_client: **402 "credits depleted"** canlı sorunu eklendi; `TWITTER_QUERY`
  okunmuyor iddiası doğrulandı → **okunuyor** (düzeltildi).
- symbols: `is_known` ekleme kapısının kaldırıldığı belgelendi (KNOWN yalnız eşleme için).
- known_issues: F6/F7/F8 yeni özellikler; **🔴 Tweet alarmı 402** kök-neden bölümü;
  `TWITTER_QUERY` dead-config maddesi çözüldü olarak işaretlendi.
- architecture_overview: `ui_scale.json`/`ui_geom.json` UI-tercih kalıcılığı eklendi.

**Çelişki/boşluk kapatma:** "TWITTER_QUERY dead config" (2 sayfada) gerçekle çelişiyordu
— kod okundu, çözüldü olarak işaretlendi. "sağ kenarda konumlanır" ifadesi sağ-alta
yaslama gerçeğiyle güncellendi.

**Teşhis sonucu:** Tweet alarmı = 𝕏 sekmesi kırmızı rozeti (`_tw_unread`) + `_tw_hl`
vurgu; kod çalışıyor ama X API 402 kredi tükenmesi nedeniyle akış boş. Kod dışı çözüm
(plan/kredi yenile veya kredili token).

**Lint (sonrası):** backlinks 9 sayfa + index yenilendi; broken_links/orphans/
missing_summary/missing_frontmatter/stale/stubs = 0.

---

## 2026-08-13 (2) — Twitter/X → Nitter RSS köprüsü senkronu

**Yeni kaynak:** `sources/05_nitter_rss_2026-08-13.md` (Nitter köprüsü + canlı instance probe, immutable).

**Kod (bu oturum):** `twitter_client.py` içi X API v2 (402) yerine **Nitter search RSS**'e
çevrildi; `fetch_recent`/`fetch_ids` + `(data,err)` sözleşmesi korundu (overlay/logic/testler
değişmedi). `config.NITTER_INSTANCES` (sır değil, çoklu fallback), `overlay._twitter_token()`
→ `True`. 12 twitter testi + toplam 215 test yeşil; `stocks.json` md5 değişmedi (veri korundu).

**Wiki güncellemeleri:**
- twitter_client: X API v2 402 açıklaması → Nitter RSS köprüsü (`_instances`/`_clean_query`/
  `_fetch_rss`/`_parse_item`, çoklu instance fallback, 429 backoff); canlı "public instance'lar
  kapalı" durumu.
- known_issues: 🔴 402 bölümü → 🟡 "Nitter RSS köprüsüne taşındı" (402 gitti); kalan engel =
  public Nitter instance'larının kapalı olması (kendi instance önerisi).
- architecture_overview: modül haritası twitter_client satırı Nitter RSS'e güncellendi;
  `NITTER_INSTANCES` config notu eklendi.

**Çelişki/boşluk kapatma:** yeni açık madde — public Nitter instance'ları anonim RSS
vermiyor (nitter.net 403, privacydev kapalı, poast/tiekoetter bot-challenge, xcancel
whitelist). Köprü kodu doğru; veri akışı instance sağlığına bağlı. Güvenilir ücretsiz yol:
kendi Nitter instance'ı (Docker) + `NITTER_INSTANCES`.

**Lint (sonrası):** backlinks 9 sayfa + index yenilendi; broken_links/orphans/
missing_summary/missing_frontmatter/stale/stubs = 0.

---

## 2026-08-13 (3) — Hisse taşıma menüsü + Kâr/Zarar (tutar & %) senkronu

**Yeni kaynak:** `sources/06_reorder_pnl_2026-08-13.md` (taşıma + K/Z oturumu, immutable).

**Kod (bu oturum):** `logic.py` — `sanitize_stocks`'a `qty` + yeni saf fonksiyon
`compute_pnl(entry, price, qty)→(amount, pct)`. `overlay.py` — `TargetSheet`'e **Adet**
alanı (`_save` 4'lü tuple); `StockRow` yeni `move_requested(str,int)` sinyali + sağ-tık
"Yukarı/Aşağı taşı", `levels_changed` 4-arg (qty), yeni `lbl_pnl` etiketi (`_sync_target`
→ `compute_pnl`); `OverlayWindow._rebuild_rows` qty + `move_requested.connect(_move_stock)`,
`_update_levels` qty. 230 test yeşil (215+15); `stocks.json` md5 değişmedi (veri korundu).

**Wiki güncellemeleri:**
- stock_row: bayat `reorder_started` → `move_requested`; layout'a K/Z(96px) sütunu;
  yeni "Kâr/Zarar etiketi" + "hedef/adet" bölümleri; `levels_changed` 4-arg.
- overlay_window: yeni "Hisse yönetimi (hedef/adet/taşıma)" bölümü; `TargetSheet` Adet;
  2026-08-13 fix satırı; source 06.
- known_issues: F9 (taşıma menüsü) + F10 (K/Z tutar&%) eklendi; source 06.
- architecture_overview: `stocks.json` şemasına `qty` + `sanitize_stocks` güvence notu.

**Çelişki/boşluk kapatma:** `stock_row.md`'deki `reorder_started` sinyali koddan
kalkmıştı (artık `move_requested`) — gerçeğe çekildi. K/Z yalnız tooltip'te %'ydi;
artık satırda tutar+% görünür (compute_pnl merkezî).

**Lint (sonrası):** backlinks + index yeniden üretilecek; hedef broken_links/orphans/
missing_summary/missing_frontmatter/stale/stubs = 0.

---

## 2026-08-14 — VİOP çarpanı + ABD hisseleri (NYSE/NASDAQ) + pill fix

**Kaynak:** `sources/07_oturum_2026-08-14.md` (immutable snapshot).

**Güncellenen Layer 2 sayfaları (5):**
- symbols: `US_SYMBOLS` ters harita + çözümleme önceliği (SPECIALS→BIST→US→fallback),
  `is_us`, `_load` 3-tuple, ABD hisse desteği bölümü.
- data_fetcher: `fetch_tv_prices` tam-sembol eşleme fix'i (NYSE:KO vs BIST:KO çakışması),
  fetch_all US açıklaması, RSI "exceed limit" notu.
- stock_row: iki-satırlı layout (meta satırı), yüzde pill düzeltmesi, VİOP çarpanı (mult),
  `levels_changed` 5-arg.
- overlay_window: TargetSheet Çarpan alanı, `_update_levels(...mult)`, 2026-08-14 fix'leri,
  sekme açıklaması (BIST+ABD).
- architecture_overview: modül haritası (symbols US + twitter RSSHub), stocks.json şema
  (`mult`), NITTER_INSTANCES→RSSHUB_URL notu.

**Çelişki/boşluk kapatma:** stock_row layout'u bayattı (K/Z+RSI ayrı sağ sütun sanılıyordu;
gerçekte artık ana satır altındaki meta satırında). architecture_overview'da twitter_client
hâlâ "Nitter" diyordu → RSSHub'a çekildi (kod 2026-08-13'te geçmişti).

**Lint (sonrası):** broken_links/orphans/missing_summary/missing_frontmatter/stale/stubs = 0.
Backlinks 9 sayfada tazelendi, index yeniden üretildi.

## 2026-08-14 — DeepR 4. tur review + tüm bulguların düzeltilmesi
- **Review:** DeepR skill (Workflow, 92 ajan, 11 boyut, adversarial doğrulama) → 28 doğrulanmış bulgu. Kullanıcı "tüm bulguları yap" dedi.
- **Kaynak:** `sources/08_deepr_review_round4_2026-08-14.md` (immutable snapshot).
- **Giderildi (G56–G69, 14 kalem):** kritik veri-kaybı yolları öncelikli.
  - G56 (KRİTİK): stocks.json bozuk-dosyada sessiz `[]` → portföy kaybı. `.corrupt.<n>` yedeği + save-bloklama bayrağı + açılış uyarısı.
  - G57 (YÜKSEK): not silme onay diyaloğu (`QMessageBox`, geri alınamaz uyarısı).
  - G58 (YÜKSEK): .app bundle US eşlemesi bozuktu (`AAPL→BIST:AAPL`); bundle senkronlandı (`→NASDAQ:AAPL`), `install.sh`'a `cmp -s` senkron kapısı.
  - G59–G67: tw_ago naive-datetime crash, SEP-önekli sembol reddi (`is_valid_user_symbol`), negatif/sıfır adet-çarpan doğrulaması, Twitter paralel fetch (ThreadPool) + poll backoff, TV auth token invalidasyonu, sanitize_stocks inf/nan filtresi, ölü kod (fetch_tv_rsi/BEARER_TOKEN), docstring/dead-return temizliği.
  - G69: test kapsamı +27 (auth token, config sır/Keychain, yeni test_paths.py, logic yeni fonksiyonlar); 2 totolojik test gerçek fonksiyonu sürecek şekilde düzeltildi.
- **Doğrulama:** `pytest -q` → 279 passed (252→279); `ruff check .` → temiz.
- **Teknik borç (kullanıcı kararı — DOKUNULMADI):** overlay.py God-module (2883 satır) ve `_rebuild_rows` O(n). Yüksek regresyon riskli refactor; `known_issues.md` "Orta/Düşük (açık)" altında resmileştirildi. storage.py ayrımı öneri olarak not edildi.
- **Güncellenen Layer 2:** known_issues (4. tur bölümü + açık-madde listesi güncellendi).
- Backlinks 9 sayfada tazelendi, index yeniden üretildi.
