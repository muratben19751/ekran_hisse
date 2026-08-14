---
title: StockRow
type: entity
summary: Tek bir hisseyi gösteren satır widget'ı; sembol + pseudo-HA sparkline + fiyat + yüzde-pill'i ana satırda, kâr/zarar (tutar & %) ve RSI alttaki meta satırında; sağ-tık menüsünden hedef/adet/çarpan, taşıma ve kaldırma.
sources:
  - sources/01_proje_ozet.md
  - sources/06_reorder_pnl_2026-08-13.md
  - sources/07_oturum_2026-08-14.md
last_updated: 2026-08-14
---

# StockRow

`overlay.py` → `StockRow(QWidget)`. Hisse panelindeki her satır.

## Layout (2026-08-14 — iki satırlı)
Dış `QVBoxLayout`: **ana satır** (`top`, sabit 26px) + opsiyonel **meta satırı**.
```
top:  [Sembol(60px)] [Sparkline(flex)] [Fiyat(70px)] [%Pill(48px, ortalı)]
meta: [K/Z] ............................................. [RSI]   (girintili)
```
- Meta satırı yalnızca PnL veya RSI verisi varken görünür; satır yüksekliği o zaman
  **26 → 40** px olur (`_sync_height`, `isHidden()` ile parent gizliyken de doğru).
- Eski tek-satırlı düzen (K/Z + RSI ayrı sağ sütunlar) 300px panelde ana satırı
  sıkıştırıyordu; meta satırına indirilerek ana satır ferahlatıldı.
- Hover, sürükle-bırak (reorder), sağ-tık context menu destekli.

## Yüzde pill'i (2026-08-14 fix)
`lbl_pct` dolgulu kapsül (yeşil `C_GREEN`/`C_GREEN_INK`, kırmızı `C_RED`/`C_RED_INK`).
**Sorun:** pill sabit yüksekliği olmadığından (10pt Bold + `padding`) 1.4x ölçekte
satırı dikey zorluyor, komşu satıra taşıyordu; `border-radius` sabitken genişlik
ölçekliydi → oran bozuk.
**Çözüm:** `setFixedSize(_sf(48), _sf(18))` (satıra oturan sabit kapsül),
`border-radius = self._pill_h // 2` (gerçek pill), layout'ta `Qt.AlignVCenter`
(dikey ortala), `padding` kaldırıldı. `update_data`'nın nötr (—) ve yeşil/kırmızı
dalları aynı radius'u kullanır.

## Hedef + adet + çarpan sistemi
`entry` / `exit` fiyat seviyeleri, **`qty` (adet)** ve **`mult` (çarpan, 2026-08-14)**
atanabilir — tümü `TargetSheet` (sağ-tık → "Hedef belirle…") üzerinden girilir,
`stocks.json`'a yazılır (bkz. [[overlay_window]]). Çıkış hedefine ulaşıldığında sarı
arka plan + dot; yön farkındalıklı (long `≥`, short `≤`).
**Fix (2026-08-07):** `entry=0` iken PnL hesaplanmıyordu (`and self._entry` sıfırı
falsy sayıyordu); artık merkezî `logic.compute_pnl` `entry == 0`'ı güvenle ele alır.

## VİOP çarpanı (mult, 2026-08-14)
VİOP kontratlarında 1 kontrat = 100 birim. `TargetSheet`'in **"Çarpan"** alanı
(sembol başına serbest; boş/1 = normal hisse, 100 = VİOP) `stocks.json`'a `mult`
olarak yazılır. `StockRow._mult` tutulur, `logic.compute_pnl(entry, price, qty, mult)`
ile K/Z **tutarını** ölçekler: `amount = (price-entry)*qty*mult`. **Yüzde, fiyat ve
hedefleri ETKİLEMEZ** — yalnız tutar. `mult` None/geçersiz/≤0/bool ise 1 sayılır.
Şema geriye uyumlu (eski mult'suz kayıtlar sorunsuz açılır).

## Kâr/Zarar etiketi (meta satırı)
`_sync_target`, `logic.compute_pnl(entry, price, qty, mult)` ile K/Z hesaplar ve
meta satırındaki `lbl_pnl` etiketine yazar (yeşil kâr / kırmızı zarar):
- **Giriş + adet** varsa: `"±<tutar> · ±%<yüzde>"` (örn. `+1.250,00 · +%8,3`).
- **Giriş var, adet yok** ise: yalnız `"±%<yüzde>"` (tutar hesaplanmaz).
- **Giriş yok** ise etiket gizli — sade satır görünümü korunur.
Aynı metin tooltip'e de eklenir. `compute_pnl` saf/Qt-bağımsız olduğundan
birim-testlidir (bkz. `sources/06_reorder_pnl_2026-08-13.md`, `07_oturum_2026-08-14.md`).

## Sinyaller
- `remove_requested(str)` — listeden kaldır
- `levels_changed(str, object, object, object, object)` — hedef **+ adet + çarpan**
  güncelle (2026-08-14: 5. argüman `mult` eklendi; 2026-08-13'te 4. `qty` eklenmişti)
  → `OverlayWindow._update_levels`
- `move_requested(str, int)` — sağ-tık "Yukarı taşı"/"Aşağı taşı"; `-1`/`+1` yön →
  `OverlayWindow._move_stock` (index takası + `save_stocks` + rebuild). Grup
  başlığındaki (`GroupHeader.move_requested`) desenin hisse satırına taşınmış hâli.

## RSI gösterimi
`update_rsi({5: x, 15: x, 30: x, 60: x})` → meta satırındaki `lbl_rsi`:
- Format: `5m:62  15m:58  30m:55  60m:51`
- Renk: RSI ≥70 → yeşil (`C_GREEN`), ≤30 → kırmızı (`C_RED`), arası → gri (`C_TEXT3`)
- Veri yoksa (veya tümü NaN) etiket gizlenir; meta satırı PnL de yoksa tamamen gizli.

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
