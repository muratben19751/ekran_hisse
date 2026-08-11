---
source: DeepR çok-boyutlu review (11 boyut × adversarial doğrulama)
retrieved: 2026-08-11
type: review_report
immutable: true
---

# DeepR Review — 2026-08-11

148 ajan, 64 hayatta kalan bulgu. Oturumda uygulanan fixler aşağıda.

## Kritik (3 fix)
- `update_rsi`: `or` zinciri → `next(...is not None)` — NoneType/falsy-zero TypeError giderildi (overlay.py:759)
- `fetch_notes None→[]`: lambda dönüşümü kaldırıldı; `apply_notes` artık `None` alıp "Bağlantı hatası" gösteriyor (overlay.py:2189)
- `price=0.0 falsy-zero`: `lp if lp is not None else last_price` + `if price is not None` (data_fetcher.py:143,147)

## Yüksek (5 fix)
- `_fetching` bayrağı `try/finally` ile her durumda temizleniyor (overlay.py:2147)
- `_NSScreen` gereksiz import kaldırıldı; `_COLLECTION_BEHAVIOR` modül düzeyinde tek sabit (overlay.py:17)
- `GIST_ID` boşken lazy URL + `ValueError` erken hata (notes_api_client.py:9)
- `StockPickerSheet._ok()` `_BIST_SYMBOLS` kontrolü eklendi — rastgele sembol enjeksiyonu engellendi (overlay.py:467)
- `_apply_float`/`_reposition_to_screen` tekrar eden AppKit import'ları temizlendi (overlay.py)

## Orta/Düşük (10+ fix)
- `_calc_rsi` flat hisse → `None` (yanıltıcı `100.0` değil) (data_fetcher.py:192)
- `_run_specials_bulk` dead code `sym_by_ticker` kaldırıldı; NaN/ZeroDivision koruması eklendi
- `compute_unread active=True` artık gerçekten `set()` döndürüyor (logic.py:71)
- `YKBK` → `YKBNK` düzeltildi (_BIST_SYMBOLS)
- `datetime` modül düzeyine taşındı (3 yerel import kaldırıldı)
- `main.py` lock dosyası `try/except` ile güvenceye alındı
- Eski geliştirme notu docstring temizlendi

## Yeni özellikler (bu oturumda eklendi)
- `⬆` floating/always-on-top toggle butonu — başlık satırında, `📌` yanında
- `⊞` monitörler arası taşıma butonu — tek monitörde gizli
- Başlık satırından sürükleyerek pencereyi istediğin yere taşıma
- Floating açıkken dışarı tıklamada panel kapanmaz
- `_current_sc` ile animasyon closure monitör-aware hale getirildi

## Açık kalan bulgular (uygulanmadı)
- E2E test hiç yok
- `_twitter_render` / `_rebuild_rows` full rebuild (performans)
- `TargetBar` ölü kod
- Twitter sembol sayısı limitsiz (512 byte API sınırı)
- `notes_api.php` ölü dosya
- Lint/tip aracı (ruff/mypy) kurulu değil
