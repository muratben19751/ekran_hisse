---
title: StockRow
type: entity
summary: Tek bir hisseyi gösteren satır widget'ı; sembol, pseudo-HA sparkline, fiyat, %değişim, kâr/zarar (tutar & %) ve RSI etiketleri; sağ-tık menüsünden hedef/adet, taşıma ve kaldırma.
sources:
  - sources/01_proje_ozet.md
  - sources/06_reorder_pnl_2026-08-13.md
last_updated: 2026-08-13
---

# StockRow

`overlay.py` → `StockRow(QWidget)`. Hisse panelindeki her satır.

## Layout
```
[Sembol(60px)] [Sparkline(flex)] [Fiyat(70px)] [%Değişim(46px)] [K/Z(96px)] [RSI(80px)]
```
Yükseklik: 26 px. Hover, sürükle-bırak (reorder), sağ-tık context menu destekli.

## Hedef + adet sistemi
`entry` / `exit` fiyat seviyeleri ve **`qty` (adet, 2026-08-13)** atanabilir —
tümü `TargetSheet` (sağ-tık → "Hedef belirle…") üzerinden girilir, `stocks.json`'a
yazılır (bkz. [[overlay_window]]). Çıkış hedefine ulaşıldığında sarı arka plan + dot;
yön farkındalıklı (long `≥`, short `≤`).
**Fix (2026-08-07):** `entry=0` iken PnL hesaplanmıyordu (`and self._entry` sıfırı
falsy sayıyordu); artık merkezî `logic.compute_pnl` `entry == 0`'ı güvenle ele alır.

## Kâr/Zarar etiketi (2026-08-13)
`_sync_target`, `logic.compute_pnl(entry, price, qty)` ile K/Z hesaplar ve `lbl_pnl`
etiketine yazar (yeşil kâr / kırmızı zarar):
- **Giriş + adet** varsa: `"±<tutar> · ±%<yüzde>"` (örn. `+1.250,00 · +%8,3`).
- **Giriş var, adet yok** ise: yalnız `"±%<yüzde>"` (tutar hesaplanmaz).
- **Giriş yok** ise etiket gizli — sade satır görünümü korunur.
Aynı metin tooltip'e de eklenir. `compute_pnl` saf/Qt-bağımsız olduğundan
birim-testlidir (bkz. `sources/06_reorder_pnl_2026-08-13.md`).

## Sinyaller
- `remove_requested(str)` — listeden kaldır
- `levels_changed(str, object, object, object)` — hedef **+ adet** güncelle
  (2026-08-13: 4. argüman `qty` eklendi) → `OverlayWindow._update_levels`
- `move_requested(str, int)` — **(2026-08-13)** sağ-tık "Yukarı taşı"/"Aşağı taşı";
  `-1`/`+1` yön → `OverlayWindow._move_stock` (index takası + `save_stocks` + rebuild).
  Grup başlığındaki (`GroupHeader.move_requested`) aynı desenin hisse satırına
  taşınmış hâli. (Eski `reorder_started` sinyali kullanımdan kalktı; taşıma artık
  menü + mevcut sürükle-bırak ile yapılır.)

## RSI gösterimi
**2026-08-07 itibarıyla aktif.** `update_rsi({5: x, 15: x, 30: x, 60: x})`:
- Sağ kenarda 80px genişlikte `lbl_rsi` etiketi
- Format: `5m:62  15m:58  30m:55  60m:51`
- Renk: RSI ≥70 → yeşil (`C_GREEN`), ≤30 → kırmızı (`C_RED`), arası → gri (`C_TEXT3`)
- Veri yoksa (veya tümü NaN) etiket gizlenir

## İlgili
- [[sparkline]]
- [[overlay_window]]
- [[data_fetcher]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[known_issues]]
- [[overlay_window]]
- [[sparkline]]
<!-- BACKLINKS:END -->
