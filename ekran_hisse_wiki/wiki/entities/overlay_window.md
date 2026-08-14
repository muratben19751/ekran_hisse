---
title: OverlayWindow
type: entity
summary: Ana pencere widget'ı; şeffaf macOS overlay olarak sağ-alta yaslı açılır, hisse/Twitter/not sekmelerini barındırır; floating, monitör geçişi, sürükleme, kenar/köşe boyutlandırma ve font ölçekleme destekler.
sources:
  - sources/01_proje_ozet.md
  - sources/02_deepr_review_2026-08-11.md
  - sources/04_oturum_2026-08-13.md
  - sources/06_reorder_pnl_2026-08-13.md
  - sources/07_oturum_2026-08-14.md
last_updated: 2026-08-14
---

# OverlayWindow

`overlay.py` içindeki ana widget. PySide6 `QWidget` tabanlı, macOS'ta şeffaf bir
overlay olarak ekranın **sağ-alt** köşesine yaslı konumlanır. Sekme çubuğu (◧/✎/𝕏)
ile açılıp kapanır.

## Sekmeler
- **Hisse (◧)** — BIST + ABD (NYSE/NASDAQ) hisse takip listesi, fiyat + sparkline + RSI
- **Notlar (✎)** — GitHub Gist üzerinden senkronlanan not paneli
- **Twitter/X (𝕏)** — Takip edilen sembollerin tweet akışı (RSSHub köprüsü, bkz. [[twitter_client]])

## Başlık satırı kontrolleri (2026-08-11)
Her sayfanın başlık satırında üç buton bulunur:
- **📌** — Panel'i açık tut (`_pinned`); odak kaybında kapanmaz
- **⬆** (mavi=aktif) — Floating/always-on-top toggle; `_toggle_float()` → Qt flag + NSWindow level 1001
- **⊞** — Monitörler arası taşıma; tek monitörde gizli

## Sürükleme (2026-08-11)
Başlık satırı widget'ına `mousePressEvent/Move/Release` bağlı; pencere serbestçe taşınabilir.
Taşıma sırasında `self._current_sc` güncellenir.

## Kenar/köşe boyutlandırma + kalıcılık (2026-08-13)
Pencere sağ-alta yaslı frameless HUD olduğundan boyutlandırılabilir kenarlar
**SOL** (genişlik), **ÜST** (yükseklik, yukarı büyür) ve **SOL-ÜST köşe**. Sağ
kenardaki sekme şeridi ve alt kenardaki ekran-yaslaması sabit kalır.
- OverlayWindow düzeyinde `mousePressEvent`/`mouseMoveEvent`/`mouseReleaseEvent`
  + `_hit_zone(pos)` (yerel koordinat → `'left'`/`'top'`/`'topleft'`/`None`),
  `RESIZE_MARGIN=6` px yakalama. İmleç: SizeHor/SizeVer/SizeFDiag.
- Sürüklerken sağ (`r0.right()`) ve alt (`r0.bottom()`) kenar sabit tutulur; sol/üst
  kenar hareket eder. Sınırlar: genişlik `PANEL_W_MIN=220`–`PANEL_W_MAX=900`,
  yükseklik `WIN_H_MIN=200`–ekran alanı (kırpma otomatik).
- **Kalıcılık:** release'te `save_geom(self._panel_w, self._win_h)` →
  `~/.ekranhisse/ui_geom.json`; açılışta `load_geom()` (font-ölçeği
  `ui_scale.json` desenini yansıtır). Sabit `PANEL_W`/`ekran//2` yerine çalışma
  zamanı `self._panel_w`/`self._win_h`; `_toggle` animasyonu,
  `_reposition_to_screen` ve `_SheetDialog._place` bu değeri kullanır (bkz. [[paths]]).
- Resize sırasında "dışarı tık = kapat" dört yolun (`eventFilter`, `changeEvent`,
  NS global monitor, `_check_outside_click`) hepsinde `_resize_edge` guard'ıyla
  devre dışı — panel resize sürüklemesinde kapanmaz.

## Font ölçekleme (A−/A+)
Başlık satırındaki `A−`/`A+` butonları global `_FONT_SCALE` çarpanını değiştirir
(0.8–1.8 arası). `_f()` tüm fontları, `_sf()` sabit satır/sütun boyutlarını bu
çarpanla ölçekler (büyük fontta kırpılmayı önler). Ölçek `~/.ekranhisse/ui_scale.json`'a
kalıcı; değişince `_font_cache` temizlenir ve `_rebuild_all_pages()` sayfaları taze
ölçekle yeniden kurar — **hiçbir kullanıcı verisi silinmez** (portföy/notlar/twitter
bellek+diskten yeniden doğar).

## Floating / Always-on-Top (2026-08-11)
- `self._floating = True` varsayılan
- Floating açıkken: `_toggle`, `changeEvent`, `eventFilter`, global mouse monitor — hepsi panel'i kapatmaz
- `keep_top` QTimer (15 sn): `window._floating and _set_window_level(window)`

## Monitör yönetimi (2026-08-11)
- `self._current_sc` — aktif ekranın geometrisi; animasyon closure ve NSEvent koordinat dönüşümü kullanır
- `_cycle_monitor()` → `QApplication.screens()` döngüsü → `_reposition_to_screen(screen)`
- `_COLLECTION_BEHAVIOR` modül düzeyinde tek sabit (DRY; `_NSScreen` import'u kaldırıldı)

## Veri akışı
`_AppSignals` nesnesi üzerinden thread-safe signal/slot:
- `data_signal` → `apply_data()` — fiyat sonuçları (`try/finally` ile `_fetching` her durumda temizlenir)
- `notes_signal(object)` → `apply_notes()` — `None` hata sinyali olarak taşınır; "Bağlantı hatası" gösterilir
- `rsi_signal` → `apply_rsi()` — RSI sonuçları (5/15/30/60 dk)

## Timer'lar
- Fiyat: 60 sn (`REFRESH_INTERVAL_MS`)
- RSI: 5 dk, başlangıçta 3 sn gecikme
- Twitter poll: 60 sn
- Outside-click fallback: 150 ms (global monitor aktifse durur)

## Hisse yönetimi (hedef / adet / çarpan / taşıma)
Her [[stock_row]] sağ-tık menüsünden yönetilir:
- **Hedef belirle…** → `TargetSheet` (giriş / çıkış / **adet** / **çarpan**). Adet
  (2026-08-13) ve çarpan (2026-08-14) opsiyoneldir; girilirse `logic.compute_pnl`
  tutar-bazlı K/Z hesaplar (`amount = (price-entry)*qty*mult`). Sheet genişliği
  360→460 (4 alan). Sonuç `("save", entry, exit_, qty, mult)` →
  `StockRow.levels_changed(5 arg)` → `OverlayWindow._update_levels(sym, e, x, qty, mult)`
  → `stocks.json` (`entry`/`exit`/`qty`/`mult`).
- **Hedefi temizle** → dördünü de `None` yapar.
- **Yukarı/Aşağı taşı** (2026-08-13) → `StockRow.move_requested(sym, ±1)` →
  `_move_stock`: `self.stocks` içinde komşu index takası + `save_stocks` +
  `_rebuild_rows` + `_apply_cached_prices`. Aynı handler grup başlığı taşımasında da
  kullanılır (DRY). Sürükle-bırak (`RowsHost.dropped` → `_on_dropped`) yöntemi de
  korunur; menü onu keşfedilebilir kılar.

## Önemli fixler

### 2026-08-14
- **VİOP çarpanı:** `TargetSheet`'e "Çarpan" alanı (sembol başına serbest, boş/1=normal,
  100=VİOP) → `logic.compute_pnl(entry, price, qty, mult)` yalnız K/Z **tutarını**
  ölçekler (yüzde/fiyat/hedef değişmez). `levels_changed` 5-arg, `_update_levels`
  `mult`'u `stocks.json`'a yazar. Şema geriye uyumlu (bkz. [[stock_row]]).
- **ABD hisseleri (NYSE/NASDAQ):** prefix'siz sembol otomatik çözümlenir (bkz.
  [[symbols]] + [[data_fetcher]]); ekleme akışı (`_add_from_search`) değişmedi —
  `AAPL` yazılır, `tv_symbol` `NASDAQ:AAPL`'a çözer. `stocks.json` düz `"AAPL"` saklar.
- **Yüzde pill'i düzeltmesi:** `lbl_pct` sabit boyut + radius=yükseklik/2 + dikey
  ortala → 1.4x ölçekte kutular satıra oturur, komşu satıra taşmaz (bkz. [[stock_row]]).

### 2026-08-13
- Kenar/köşe boyutlandırma + `ui_geom.json` kalıcılığı eklendi (yukarıda); `PANEL_W`/`ekran//2` sabitleri → çalışma zamanı `self._panel_w`/`self._win_h`
- Font ölçekleme (A−/A+) + `ui_scale.json` — büyük/küçük yazı, `_rebuild_all_pages` ile veri-koruyan yeniden kurulum
- Sembol evreni kısıtı kaldırıldı: `_add_from_search`/`StockPickerSheet` artık `is_known` kapısı yerine biçim kontrolü (`[A-Z0-9.-]`); listede olmayan sembol de eklenip varsayılan eşlemeyle (`BIST:<SEM>`/`<SEM>.IS`) çekilir
- Hisse satırına sağ-tık **Yukarı/Aşağı taşı** + `TargetSheet`'e **Adet** alanı → satırda **kâr/zarar (tutar & %)** etiketi (bkz. yukarıda + [[stock_row]])

### 2026-08-11
- `update_rsi`: `or` zinciri → `next(...is not None)` — NoneType/falsy-zero TypeError giderildi
- `fetch_notes None→[]` lambda kaldırıldı; `apply_notes(None)` çalışıyor
- `_fetching` `try/finally` ile güvenceye alındı
- `StockPickerSheet._ok()` `_BIST_SYMBOLS` kontrolü eklendi
- `YKBK` → `YKBNK` düzeltildi
- `main.py` lock dosyası `try/except OSError` ile güvenceye alındı

### 2026-08-07
- `prev == 0` guard kaldırıldı; her sekme geçişinde veri yenileniyor
- `_tw_loading` flag guard — çoklu thread spawn engellendi
- Not kayıt callback `ok` parametresi kontrolü
- `tempfile + os.replace` atomic write
- `card.setVisible()` — collapse artık `_rebuild_rows()` tetiklemiyor
- `_set_ns_window_level` tek canonical fonksiyon

## İlgili
- [[sparkline]]
- [[stock_row]]
- [[data_fetcher]]
- [[architecture_overview]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[known_issues]]
- [[paths]]
- [[sparkline]]
- [[stock_row]]
- [[symbols]]
- [[twitter_client]]
<!-- BACKLINKS:END -->
