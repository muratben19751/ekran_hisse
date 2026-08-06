---
title: StockRow
type: entity
summary: Tek bir hisseyi gösteren satır widget'ı; sembol, pseudo-HA sparkline, fiyat ve değişim yüzdesi içerir.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-06
---

# StockRow

`overlay.py` → `StockRow(QWidget)`. Hisse panelindeki her satır.

## Layout
```
[Sembol(60px)] [Sparkline(flex)] [Fiyat(70px)] [%Değişim(46px)]
```
Yükseklik: 26 px. Hover, sürükle-bırak (reorder), sağ tık context menu destekli.

## Hedef sistemi
`entry` / `exit` fiyat seviyeleri atanabilir. Ulaşıldığında sarı arka plan ve dot.

## Sinyaller
- `remove_requested(str)` — listeden kaldır
- `levels_changed(str, object, object)` — hedef güncelle
- `reorder_started(str)` — sürükle-bırak başladı (bağlı slot yok — etkisiz)

## RSI
`update_rsi(self, rsi)` metodu tanımlı ama gövdesi yalnızca `pass` (`overlay.py:718-719`) — RSI hiçbir yerde gösterilmiyor. Veri katmanındaki tüm RSI hesabı boşa gidiyor. Bkz: [[known_issues]].

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
