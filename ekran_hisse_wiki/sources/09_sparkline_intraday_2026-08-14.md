---
source: "Oturum — Sparkline yeniden tasarımı + gerçek intraday bar serisi"
retrieved: 2026-08-14
type: session_log
immutable: true
---

# Sparkline: Çizgi + Alan Dolgusu & Gerçek Intraday Bar Serisi (2026-08-14)

Aynı gün (4. tur DeepR sonrası) iki ardışık istekle sparkline widget'ı baştan
tasarlandı ve veri kaynağı değiştirildi. Commit'ler: `a8845de` (tasarım),
`205c2c2` (intraday veri).

## 1. Tasarım değişikliği — pseudo-HA bar → çizgi + alan dolgusu (a8845de)

**Önce:** `Sparkline` pseudo Heikin-Ashi mumları çiziyordu (`_ha_candles`,
`drawRect` ile dikdörtgen mumlar; yeşil/kırmızı `ha_close >= ha_open`).

**Sonra:** Yumuşak çizgi (`QPainterPath` + `QPen`, antialiasing) + çizgi altı
degrade **alan dolgusu** (`QLinearGradient`, tepe alpha 90 → dip alpha 0) + son
noktayı (anlık fiyat) vurgulayan dolu daire (`drawEllipse`). Renk yön işaretidir:
`pts[-1] >= pts[0]` → yeşil (`C_GREEN`), aksi → kırmızı (`C_RED`).
`_ha_candles` kaldırıldı.

Kullanıcı referans görseli verdi ("Çizgi sparkline + alan dolgusu — gün içi akışı
daha sakin gösterir, uç nokta anlık fiyatı vurgular").

Yeni QtGui importları: `QBrush`, `QLinearGradient`, `QPainterPath`, `QPen`;
QtCore: `QPointF`.

## 2. Veri kaynağı — biriktirilen snapshot → gerçek intraday bar serisi (205c2c2)

**Önce (soru: "hangi timeframe?"):** Sparkline sabit bir borsa timeframe'i
DEĞİLDİ. `fetch_tv_prices`'ın `lp` (anlık son fiyat) değeri her fiyat
yenilemesinde (`REFRESH_INTERVAL_MS = 60_000`, 60 sn) `spark.push(price)` ile
ekleniyordu; `MAX = 24` → son ~24 dakikalık kayan pencere. Açılışta boştu,
dolması ~24 dk sürüyordu; her nokta close değil anlık fiyattı.

**Kullanıcı kararı:** "gerçek olan" → gerçek intraday mum serisi. AskUserQuestion
ile netleşen seçim: **5 dakika × 24 bar (son ~2 saat)**, **son barı güncelle**
(canlı fiyat son noktanın yerine yazılır, pencere kaymaz), **periyodik 5 dk**
tazeleme.

**Sonra:**
- `data_fetcher.fetch_tv_history(symbols, interval=5, bars=24)` eklendi. RSI'ın
  `create_series` altyapısını paylaşır (aynı tek WS bağlantısı, `resolve_symbol`
  + `create_series`), ama `_calc_rsi` yerine son N ham close döndürür:
  `{SEMBOL_UPPER: [close_eski..close_yeni]}`. NaN barları eler; `series_error`/
  `symbol_error`/`series_completed` ile pending yönetimi RSI ile birebir.
  `_TV_INTERVALS = {5,15,30,60}` içinde 5 mevcut olduğu için ek sabit gerekmedi.
- `Sparkline.restore(points)`: gerçek barlarla tohumlar, `_has_history=True`
  set eder; boş/tümü-NaN gelirse mevcut noktaları KORUR (grafiği boşaltmaz).
- `Sparkline.set_live(price)`: `_has_history` ise SON noktayı canlı fiyatla
  GÜNCELLER (pencere kaymaz, TV barıyla hizalı); geçmiş yoksa eski kayan-pencere
  davranışına (append) düşer. `update_data` artık `push` yerine `set_live` çağırır.
- Orkestrasyon (`overlay.py`): `hist_result = Signal(object)` + `_hist_refresh`
  worker (arka plan thread, TV WS ana thread'i bloklamaz) + `_on_hist_result`
  (ana thread'de her satırın `spark.restore()` + `_spark_history[sym]` güncelle).
  `_hist_timer` 5 dk; açılışta `singleShot(1500)`; hisse paneline geçişte
  `singleShot(700)`. `_hist_fetching` re-entrancy guard.

## Doğrulama
- `python3 -m ruff check .` → temiz.
- `python3 -m pytest -q` → **284 passed** (279 → 284, +5 sparkline testi:
  restore tohumlama, boş/NaN koruması, set_live son-bar güncelleme, fallback,
  None/NaN guard).
- Offscreen render (yükseliş/düşüş/NaN) doğrulandı; bundle senkron (install.sh
  cmp -s), uygulama yeniden başlatıldı.

## Not
- `push()` metodu geriye dönük uyumluluk için korundu ama artık üretim yolunda
  çağrılmıyor (yerini `set_live` aldı).
- Her nokta hâlâ piyasa kapalıyken sabit kalır (intraday bar akmaz) — bu beklenen.
