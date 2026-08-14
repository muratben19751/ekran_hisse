---
title: Bilinen Sorunlar
type: synthesis
summary: EkranHisse'de dört DeepR review turuyla (2026-08-06/11/12/14) tespit edilen bug'lar + teknik borç. 4. tur (2026-08-14) 28 doğrulanmış bulgunun tümü düzeltildi (mimari refactor hariç); kritik veri-kaybı yolları (stocks.json bozuk-dosya + not silme onayı) kapatıldı, .app bundle US eşlemesi senkronlandı.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
  - sources/03_deepr_review_round2_2026-08-12.md
  - sources/04_oturum_2026-08-13.md
  - sources/05_nitter_rss_2026-08-13.md
  - sources/06_reorder_pnl_2026-08-13.md
  - sources/08_deepr_review_round4_2026-08-14.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-14
---

# Bilinen Sorunlar

Üç DeepR review turu (2026-08-06, 2026-08-11, 2026-08-12) ile ortaya çıkan sorunlar. Commit `b802327` (2026-08-07) ilk turu, `d8de974`/oturum (2026-08-11) ikinci turu, `e54430b` (2026-08-12) üçüncü turu kapatmıştır. Üçüncü tur tamamı **adversarial doğrulamadan** geçti (`unfixed_count: 0`).

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

## ✅ Giderilen (2026-08-12, 3. tur — commit e54430b, adversarial doğrulandı)

| # | Sorun | Düzeltme |
|---|-------|----------|
| G34 | Sheet dialog açılınca panel modal-kör kapanıyordu | `_modal_open()` guard (4 kapanma yolu) + test |
| G35 | TV WS NaN fiyat → sparkline paint çökmesi (`float('nan') is not None`) | `data_fetcher` isnan filtresi + `Sparkline.push` NaN/None guard |
| G36 | Twitter poll hatası yutuluyordu | `tw_poll_error` Signal + status/log |
| G37 | Fiyat var ama `change_pct` None ise sparkline güncellenmiyordu | `push` koşulsuz (if/else dışına) |
| G38 | Hedef girişi geçersiz sayıda sessizce None kaydediyordu | `_INVALID` sentinel + kırmızı kenar + accept reddi |
| G39 | Silinip yeniden eklenen hisse bayat fiyat | `_last_data.pop(symbol)` |
| G40 | Floating modda monitör değişince panel görünmez | `_reposition_to_screen` genişlik senkronu |
| G41 | 𝕏 chip sayaçları çakışan sembollerde yanıltıcı | `symbols_of_tweet` (çok-sembol) |
| G42 | RSI worker `_rsi_fetching`'i ana thread dışından yazıyor | `rsi_done` Signal + `_on_rsi_done`; emit `try/finally` içinde |
| G43 | `~/.ekranhisse` üç modülde bağımsız hardcode | yeni `paths.py` (tek kaynak) |
| G44 | WS `run_forever` thread'i sızabilir | `ping_interval`/`ping_timeout` + `setdefaulttimeout` |
| G45 | TV auth token negatif sonucu cache'lenmiyor | negatif TTL cache (60 sn) |
| G46 | `_calc_rsi` warm-up bar yetersiz (24) | `_RSI_WARMUP_BARS = 150` |
| G47 | import anında sır snapshot — kurulum sırası hatası | setup.command blocking `read` + Keychain recheck |
| G48 | Doküman "Hedef rozeti"+"track" UI'da yok; `C_TRACK` ölü sabit | doküman gerçeğe çekildi + ölü sabit silindi |
| G49 | **stocks.json konumu** — bundle Resources'a yazılıyordu | `~/.ekranhisse` (`paths.py`) + `.gitignore`; migrasyon |
| G50 | **`notes_api.php` ölü PHP backend** | `notes_api.php`/`test.php` repo'dan kaldırıldı (Gist mimarisi) |
| G51 | `_twitter_render` filtre değişiminde tüm widget'ları yıkıyordu | show/hide görünürlük filtresi (`_twitter_set_filter`) |
| G52 | `XU050` `_BIST_SYMBOLS`'te var ama data_fetcher haritalarında yok | `symbols.py` tek kaynak (BIST ∪ SPECIALS = KNOWN) |
| G53 | Lint/tip aracı kurulu değil | `pyproject.toml` + `dev-requirements.txt` (ruff); "All checks passed" |
| G54 | E2E/unit test boşluğu — `OverlayWindow` hiç örneklenmiyordu | offscreen QApplication testleri (191→200) |
| G55 | Twitter API 429 için retry/backoff yok | `twitter_client.py` Retry-After + sınırlı yeniden deneme |

**Bilinçli kapsam kararı (belgeleme fix'i):** `save_notes` latest-wins çok cihazda not eziyor — gerçek ETag/CRDT merge kapsam dışı ve riskli görüldü; yalnız docstring + kullanıcı dokümanında **belgelendi**. Kod değişmedi.

---

## ✅ Yeni özellikler (2026-08-13)

| # | Özellik |
|---|---------|
| F6 | **Font ölçekleme** — başlık satırında `A−`/`A+`; `_FONT_SCALE` (0.8–1.8), `_f()`/`_sf()` ölçekler, `ui_scale.json` kalıcı, `_rebuild_all_pages` veri-koruyan yeniden kurulum |
| F7 | **Kenar/köşe boyutlandırma** — sol (genişlik) / üst (yükseklik) / sol-üst köşe sürükle; sağ+alt kenar sabit; `ui_geom.json` kalıcı; `PANEL_W`/`ekran//2` → çalışma zamanı `self._panel_w`/`self._win_h` (bkz. [[overlay_window]]) |
| F8 | **Sembol evreni kısıtı kaldırıldı** — `is_known` kapısı yerine biçim kontrolü; listede olmayan sembol de eklenip `BIST:<SEM>`/`<SEM>.IS` varsayılan eşlemesiyle çekilir (bkz. [[symbols]]) |
| F9 | **Hisse taşıma menüsü** — [[stock_row]] sağ-tık "Yukarı taşı"/"Aşağı taşı" (`move_requested(sym, ±1)` → `_move_stock` index takası + `save_stocks`); mevcut sürükle-bırak korunur, menü keşfedilebilir kılar |
| F10 | **Kâr/Zarar (tutar & %)** — `TargetSheet`'e **Adet** alanı; `logic.compute_pnl(entry, price, qty)` saf fonksiyonu; satırda yeşil/kırmızı `lbl_pnl` (giriş+adet → tutar·%, adet yok → yalnız %, giriş yok → gizli) + tooltip. `qty` `stocks.json`'a eklendi (veri korundu) |

---

---

## ✅ Giderilen (2026-08-14, 4. tur — DeepR 92 ajan, adversarial doğrulandı)

28 doğrulanmış bulgunun tümü düzeltildi (mimari refactor hariç). Detay:
`sources/08_deepr_review_round4_2026-08-14.md`.

| # | Sorun | Düzeltme |
|---|-------|----------|
| G56 | **stocks.json bozuk/OSError'da sessiz `[]` → ilk kayıtta portföy kaybı** (KRİTİK; 3 boyut bağımsız buldu) | `_stocks_load_failed` bayrağı; bozuk dosya `.corrupt.<n>` yedeklenir; `save_stocks` o oturum bloklanır; açılışta `QMessageBox` kritik uyarı |
| G57 | **Not silme anında + onaysız Gist'e** (last-write-wins, undo yok) | `_delete_note`'a `QMessageBox` onay diyaloğu (başlık gösterir, DestructiveRole) |
| G58 | **.app bundle US hisse fiyat/RSI'ını sessizce bozuyor** — bundle symbols eski (US yok, `AAPL→BIST:AAPL`) | bundle'a tüm kaynak senkronlandı (`AAPL→NASDAQ:AAPL` doğrulandı); `install.sh`'a `cmp -s` senkron doğrulaması (ayrışmada kurulum durur) |
| G59 | `tw_ago` naive datetime → TypeError, tüm tweet listesi kırılır | naive `t` → `timezone.utc` bağlanır |
| G60 | `---` önekli sembol görünmez bölüm ayracına dönüşüyor (fiyat satırı kaybolur) | yeni `logic.is_valid_user_symbol` (SEP öneki + salt-noktalama reddi); 3 çağrı yeri |
| G61 | Negatif/sıfır adet/çarpan sessizce yutuluyor (compute_pnl tutarı gizler, geri bildirim yok) | `TargetSheet._num(positive=True)` → ≤0 `_INVALID` + kırmızı işaret |
| G62 | Twitter keyword istekleri sıralı — N sembolde N× gecikme | `_fetch_items` `ThreadPoolExecutor` ile paralel (max 6), sıra korunur |
| G63 | Twitter poll hata sonrası backoff yok (RSSHub kapalıyken her 60sn boşa istek) | ardışık hatada exponential backoff (60sn→15dk cap); başarıda tabana sıfırlanır |
| G64 | **TV auth token pozitif cache süresiz** — token expire olunca fiyat/RSI sessizce boş | `_invalidate_tv_auth_token`; fetch tamamen boş sonuçta bir kez invalide + retry |
| G65 | `sanitize_stocks` inf/nan geçiriyor → 'inf'/'nan' gösterimi | `math.isfinite` filtresi; `compute_pnl` inf entry/price'ta (None,None) |
| G66 | Ölü kod: `fetch_tv_rsi` (kullanılmıyor), `TWITTER_BEARER_TOKEN` (X API v2 kaldırıldı) | `fetch_tv_rsi` bulk retry sarmalayıcısına dönüştü; BEARER_TOKEN config'ten kaldırıldı |
| G67 | `_parse_item` docstring Nitter atfı (artık RSSHub); `_fetch_one` ulaşılamayan `return` | docstring RSSHub'a güncellendi; ölü `last_err` sadeleştirildi |
| G68 | `test_overlay_ui.py` parçalı import (I001) | `ruff --fix` |
| G69 | Test kapsamı boşlukları + 2 totolojik test | +27 test: `_get_tv_auth_token`/invalidate, config sır uyarısı + Keychain dalları, yeni `test_paths.py`, `is_valid_user_symbol`/sanitize/compute_pnl/tw_ago; totolojik testler gerçek fonksiyonu sürecek şekilde düzeltildi |

**Doğrulama:** `pytest -q` → **279 passed** (252→279, +27); `ruff check .` → temiz.

**Kapsam DIŞI (kullanıcı kararı — teknik borç, aşağıya taşındı):** overlay.py
God-module ve `_rebuild_rows` O(n) yüksek regresyon riskli refactor; ertelendi.

---

## 🟡 Tweet alarmı: X API 402 → Nitter RSS köprüsü (2026-08-13)**Özgün belirti:** 𝕏 sekmesindeki alarm rozeti (`_tw_unread`) hiç dolmuyor, akış
boş. Alarm = görsel rozet + yeni tweet vurgusu (`_tw_hl`); sesli/sistem bildirimi
zaten yok.

**Kök neden:** `api.twitter.com/2/tweets/search/recent` **HTTP 402 "credits
depleted"** döndürüyordu. X API v2 `search/recent` ücretli; hesap kredisi tükenmiş
(kod değil, hesap sorunu).

**Yapılan (kod, commit bu oturum):** kullanıcı ücretsiz çözüm istedi;
[[twitter_client]] içi **Nitter search RSS köprüsüne** çevrildi — bearer token'a
bağımlılık kaldırıldı, public API korundu (`overlay`/`logic`/testler değişmedi),
`NITTER_INSTANCES` ile çoklu instance fallback eklendi. **402 tamamen gitti.**

**Kalan engel (yeni açık madde):** Canlı probe (bkz. `sources/05_nitter_rss_2026-08-13.md`)
şu an **hiçbir public Nitter instance'ının anonim RSS vermediğini** doğruladı
(nitter.net 403, privacydev kapalı, poast/tiekoetter bot-challenge, xcancel
whitelist). Köprü kodu doğru ama veri akışı instance sağlığına bağlı → bugün boş.

**Güvenilir ücretsiz yol:** **kendi Nitter instance'ını** (Docker + guest token)
kurup ekle:
`security add-generic-password -U -s ekranhisse -a NITTER_INSTANCES -w 'https://...'`
veya `~/.ekranhisse/notes_config.env`'e `NITTER_INSTANCES=...` + restart. Bkz.
[[twitter_client]].

**İkincil (hâlâ açık):** `_twitter_poll_error` hatayı yalnız 𝕏 sekmesi AÇIKKEN
status'a yazar; kapalıyken sessizce loglar (görünürlük iyileştirmesi yapılabilir).

---

## Kritik / Yüksek (hâlâ açık)

- ✅ Bu kategoride açık madde kalmadı (stocks.json ve PHP backend 3. turda kapandı).

---

## Orta / Düşük (açık)

- **Teknik borç — `overlay.py` God-module (2883 satır):** kalıcılık (load/save_stocks, _save_json, geom/scale G/Ç) + UI + thread/timer orkestrasyonu + macOS köprüsü aynı dosyada. `test_stocks_io` Qt'siz çalışamıyor. **4. turda kullanıcı "dokunma, teknik borç kaydet" dedi** (yüksek regresyon riski). Öneri: kalıcılık katmanı ayrı `storage.py`'ye çıkarılabilir.
- **Teknik borç — `_rebuild_rows` O(n):** her yapısal mutasyonda (ekle/sil/taşı/yeniden-adlandır) tüm widget'lar deleteLater + sıfırdan kurulur. Düşük şiddet (veri kaybı yok, küçük listede önemsiz); arama filtresi zaten `setVisible` ile kaçınıyor. Ertelendi (Qt yaşam-döngüsü tuzakları riskli).
- **`TargetBar`** sınıfı hiç örneklenmiyor — ölü kod (doğrula/kaldır).
- **Twitter sembol sayısı** limitsiz; ~40+ sembolde RSSHub keyword sorgusu şişebilir (artık paralel çekiliyor ama sembol başına ayrı istek).
- **Not editörü** karakter limiti yok; GitHub Gist 10 MB sınırı.
- **Çok cihaz not senkronu** last-write-wins — eşzamanlı düzenlemede kayıp (belgeli, çözülmedi). Not silme artık onay ister (G57) ama çok-cihaz merge yok.

### ✅ 4. turda çözülenler (önceki açık maddelerden)
- ~~`_rebuild_rows` tam rebuild~~ → teknik borç olarak resmileştirildi (yukarı).
- ~~TV auth token oturum süresi dolunca yenilenmiyor~~ → **çözüldü (G64):** boş sonuçta invalide+retry.
- ~~Bölüm adında `:` / SEP karakteri ayrıştırmayı bozuyor~~ → **çözüldü (G60):** `is_valid_user_symbol` SEP önekini reddediyor.

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
- [[twitter_client]]
<!-- BACKLINKS:END -->
