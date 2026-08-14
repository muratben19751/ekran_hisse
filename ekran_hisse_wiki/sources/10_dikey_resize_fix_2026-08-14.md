---
source: "Oturum — Başlık satırı üst kenardan dikey boyutlandırma düzeltmesi"
retrieved: 2026-08-14
type: session_log
immutable: true
---

# Dikey Boyutlandırma Düzeltmesi: Başlık Satırı Üst Kenar Çakışması (2026-08-14)

Kullanıcı: "uygulama ekranını dikey de uzatabilmeliyim."

## Kök neden

Dikey boyutlandırma (üst kenardan yukarı uzatma) `OverlayWindow` düzeyinde
**zaten vardı** (`_hit_zone` → `'top'`, `_perform_resize`, `WIN_H_MIN`–ekran
sınırları, `ui_geom.json` kalıcılığı). Ama pencerenin en üstünü **başlık satırı
widget'ı (`_head_row`)** kaplıyordu ve bu widget kendi `mousePressEvent`'inde
pencereyi TAŞIYORDU (`_drag_pos`), olayı üst `OverlayWindow`'a iletmiyordu.
Sonuç: üst kenardaki `RESIZE_MARGIN` px'lik dikey-resize şeridi başlık widget'ının
altında gölgeleniyordu; kullanıcı üstten uzatmaya çalışınca pencere **taşınıyordu**.

## Çözüm (overlay.py, `_head_row`)

Başlık satırının mouse handler'larına üst-kenar farkındalığı eklendi:
- `_on_top_edge(e)`: yerel `y <= RESIZE_MARGIN` mı? (başlık widget'ının y'si pencere
  içinde ~0 olduğundan yerel y yeterli).
- `_head_mouse_press`: üst kenardaysa taşıma yerine `self._resize_edge = "top"` +
  `_resize_origin` kur, `_drag_pos = None`, olayı tüket. Değilse eski taşıma.
- `_head_mouse_move`: `_resize_edge` aktifse `self._perform_resize(...)` çağır
  (dikey uzat); değilse eski taşıma; basılı değilken üst kenarda `SizeVerCursor`,
  gerisinde `SizeAllCursor` imleci göster.
- `_head_mouse_release`: `_resize_edge` aktifse `save_geom(...)` + state temizle
  (OverlayWindow.mouseReleaseEvent'in aynısı); değilse `_drag_pos = None`.
- `w.setMouseTracking(True)` — buton basılı olmadan da imleç geri bildirimi.
- `RESIZE_MARGIN` 6 → 8 px (üst kenarda yakalaması kolaylaştı).

Sol kenar (genişlik), sol-üst köşe ve OverlayWindow'un kendi `_hit_zone` yolları
değişmedi. Alt sınır `WIN_H_MIN = 200`, üst sınır ekranın kullanılabilir yüksekliği;
alt kenar sabit, pencere yukarı büyür. Boyut `ui_geom.json`'a yazılır (`win_h`),
yeniden başlatınca korunur.

## Doğrulama
- `python3 -m ruff check overlay.py` → temiz.
- `python3 -m pytest -q` → 284 passed.
- Bundle senkron (install.sh `cmp -s` ✓), uygulama yeniden başlatıldı.

## Not
- Kullanıcı verisi (stocks.json, notlar) etkilenmez — yalnız pencere geometrisi.
- Commit: bu oturumda (dikey-resize düzeltmesi).
