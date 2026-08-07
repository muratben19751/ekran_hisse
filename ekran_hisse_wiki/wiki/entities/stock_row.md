---
title: StockRow
type: entity
summary: Tek bir hisseyi gösteren satır widget'ı; sembol, pseudo-HA sparkline, fiyat, değişim yüzdesi ve RSI etiketleri içerir.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-07
---

# StockRow

`overlay.py` → `StockRow(QWidget)`. Hisse panelindeki her satır.

## Layout
```
[Sembol(60px)] [Sparkline(flex)] [Fiyat(70px)] [%Değişim(46px)] [RSI(80px)]
```
Yükseklik: 26 px. Hover, sürükle-bırak (reorder), sağ tık context menu destekli.

## Hedef sistemi
`entry` / `exit` fiyat seviyeleri atanabilir. Ulaşıldığında sarı arka plan ve dot.
**Fix (2026-08-07):** `entry=0` iken PnL tooltip hesaplanmıyordu (`and self._entry` sıfırı falsy sayıyordu); `and self._entry is not None and self._entry != 0` ile düzeltildi.

## Sinyaller
- `remove_requested(str)` — listeden kaldır
- `levels_changed(str, object, object)` — hedef güncelle
- `reorder_started(str)` — sürükle-bırak başladı; **artık `_on_reorder_started` slot'una bağlı** (`_rebuild_rows` içinde `row.reorder_started.connect(...)` çağrısı eklendi)

## RSI gösterimi
**2026-08-07 itibarıyla aktif.** `update_rsi({5: x, 15: x, 30: x, 60: x})` metodunu implement etti:
- Sağ kenarda 80px genişlikte `lbl_rsi` etiketi
- Format: `5m:62  15m:58  30m:55  60m:51`
- Renk: RSI ≥70 → yeşil (`C_GREEN`), ≤30 → kırmızı (`C_RED`), arası → gri (`C_TEXT3`)
- Veri yoksa etiket gizlenir

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
