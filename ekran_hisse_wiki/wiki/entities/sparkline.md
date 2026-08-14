---
title: Sparkline (Çizgi + Alan Dolgusu)
type: entity
summary: StockRow içinde gün-içi fiyatı GERÇEK intraday bar serisiyle (TV 5dk × 24 = son ~2 saat) çizgi + degrade alan dolgusu olarak gösteren mini grafik; canlı fiyat son barı günceller, son nokta anlık fiyatı vurgular.
sources:
  - sources/01_proje_ozet.md
  - sources/09_sparkline_intraday_2026-08-14.md
related:
  - wiki/entities/data_fetcher.md
last_updated: 2026-08-14
---

# Sparkline

`overlay.py` → `Sparkline(QWidget)`. Her `StockRow`'da gün-içi fiyat hareketini
görselleştirir. (2026-08-14 öncesi pseudo Heikin-Ashi mum çiziyordu; artık çizgi +
alan dolgusu, kaynak: `sources/09_sparkline_intraday_2026-08-14.md`.)

## Görselleştirme — çizgi + degrade alan dolgusu
`paintEvent` (antialiasing açık):
- **Çizgi:** `QPainterPath` + `QPen` (genişlik 1.4, yuvarlak uç/köşe).
- **Alan dolgusu:** çizginin altı `QLinearGradient` ile doldurulur (tepe alpha 90 →
  dip alpha 0), kapalı yol (`area.lineTo(...h)` + `closeSubpath`).
- **Son nokta:** anlık fiyatı vurgulayan dolu daire (`drawEllipse`, r≈2).
- **Renk (yön):** `pts[-1] >= pts[0]` → yeşil (`C_GREEN` #30d158), aksi → kırmızı
  (`C_RED` #ff453a). `C_GREEN_INK`/`C_RED_INK` koyu tonlar da mevcut.

## Veri kaynağı — GERÇEK intraday bar serisi
Eskiden biriktirilen anlık fiyat (`lp`) snapshot'larıydı (60 sn'de bir nokta, son
~24 dk kayan pencere — açılışta boş, close değil anlık fiyat). Artık
[[data_fetcher]] `fetch_tv_history(symbols, interval=5, bars=24)` ile TV'den
çekilen **5 dakikalık close serisi** (24 bar = son ~2 saat). Açılışta dolu gelir.

| Metot | Davranış |
|---|---|
| `restore(points)` | Gerçek barlarla TOHUMLAR; `_has_history=True`. Boş/tümü-NaN → mevcut korunur (boşaltmaz). |
| `set_live(price)` | `_has_history` ise SON noktayı canlı fiyatla GÜNCELLER (pencere kaymaz). Geçmiş yoksa append (kayan pencere fallback). `update_data` bunu çağırır. |
| `push(price)` | Eski append yolu; geriye dönük uyum için korundu, üretimde çağrılmaz. |

`None`/`NaN` fiyat tüm giriş metotlarında yok sayılır (TV WS'ten NaN sızabilir;
`int(vy(nan))` çizimi çökertirdi).

## Parametreler
| Parametre | Değer |
|---|---|
| MAX nokta | 24 |
| Timeframe | 5 dk × 24 bar (son ~2 saat) |
| Yükseklik | `_sf(14)` px |
| Çizgi genişliği | 1.4 |
| Renk (yükselen/düşen) | `C_GREEN` / `C_RED` |

## Orkestrasyon (overlay.py)
`hist_result = Signal(object)` + `_hist_refresh` worker (arka plan thread — TV WS
ana thread'i bloklamaz) + `_on_hist_result` (ana thread'de `restore` + `_spark_history`
güncelle). `_hist_timer` 5 dk; açılışta ve hisse paneline geçişte de tetiklenir;
`_hist_fetching` re-entrancy guard. Canlı fiyat (`_stocks_refresh`, 60 sn) son barı
`set_live` ile günceller.

## Geçmiş koruma
Rebuild (font/boyut değişimi) sonrası `_spark_history` dict'inden `restore(points)`
ile geri yüklenir; oturum boyunca birikim kaybolmaz.

## İlgili
- [[data_fetcher]]
- [[stock_row]]
- [[overlay_window]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[data_fetcher]]
- [[overlay_window]]
- [[stock_row]]
<!-- BACKLINKS:END -->
