---
title: Sparkline (Pseudo Heikin-Ashi)
type: entity
summary: StockRow içinde fiyat geçmişini pseudo Heikin-Ashi mumlarıyla gösteren mini grafik widget'ı.
sources:
  - sources/01_proje_ozet.md
last_updated: 2026-08-06
---

# Sparkline

`overlay.py` → `Sparkline(QWidget)`. Her `StockRow`'da fiyat geçmişini görselleştirir.

## Algoritma — Pseudo Heikin-Ashi
Gerçek OHLC bar verisi olmaksızın sadece close fiyatlarından HA türetme:

```
ha_open[0]  = close[0]
ha_close[i] = close[i]
ha_open[i]  = (ha_open[i-1] + ha_close[i-1]) / 2
```

Yeşil mum: `ha_close >= ha_open`, Kırmızı: `ha_close < ha_open`.
Gerçek HA'ya kıyasla gürültüyü azaltır, trend sürekliliğini öne çıkarır.

## Parametreler
| Parametre | Değer |
|---|---|
| MAX nokta | 24 |
| Yükseklik | 14 px |
| Mum gap | 1 px |
| Mum renk (yükselen) | `C_GREEN` (#30d158) |
| Mum renk (düşen) | `C_RED` (#ff453a) |

## Geçmiş koruma
Rebuild sonrası `_spark_history` dict'inden `restore(points, up)` ile geri yüklenir;
oturum boyunca birikim kaybolmaz.

## İlgili
- [[stock_row]]
- [[overlay_window]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
