---
source: "Oturum — DeepR 4. tur review + tüm bulguların düzeltilmesi"
retrieved: 2026-08-14
type: session_log
immutable: true
---

# DeepR 4. Tur Review + Düzeltmeler (2026-08-14)

DeepR skill'i (`Workflow`, 92 ajan, 11 boyut, adversarial doğrulama) ile
EkranHisse review edildi; 28 bulgu adversarial doğrulamadan geçti. Kullanıcı
"tüm bulguları yap" dedi; mimari refactorlar hariç tümü düzeltildi.

## Review sonucu (28 doğrulanmış bulgu)

En kritik 3:
1. **stocks.json okuma hatasında sessiz `[]` → ilk kayıtta portföy kaybı** (KRİTİK, 3 boyut bağımsız buldu).
2. **Not silme anında + onaysız Gist'e yazılıyor** (last-write-wins, undo yok) (YÜKSEK).
3. **.app bundle US hisselerinin fiyat/RSI'ını sessizce bozuyor** — bundle'daki `symbols.py`/`symbols.json` eski (US desteği yok); `AAPL → BIST:AAPL` (YÜKSEK, fiilen materyalize).

## Yapılan düzeltmeler (bu oturum)

| # | Bulgu | Düzeltme | Dosya |
|---|-------|----------|-------|
| G56 | load_stocks bozuk dosyada sessiz `[]` → veri kaybı | `_stocks_load_failed` bayrağı; bozuk dosya `.corrupt.<n>` yedeklenir; `save_stocks` o oturum bloklanır; açılışta `QMessageBox` uyarısı | overlay.py |
| G57 | Not silme onaysız + geri alınamaz | `_delete_note`'a `QMessageBox` onay diyaloğu (başlık gösterir) | overlay.py |
| G58 | .app bundle symbols eski (US bozuk) | bundle'a tüm kaynak kopyalandı (AAPL→NASDAQ:AAPL doğrulandı); `install.sh`'a `cmp -s` senkron doğrulaması eklendi | install.sh, bundle |
| G59 | tw_ago naive datetime TypeError → tweet listesi kırılır | naive `t` → `timezone.utc` bağlanır | logic.py |
| G60 | `---` önekli sembol görünmez ayraca dönüşüyor | yeni `logic.is_valid_user_symbol` (SEP öneki + salt-noktalama reddi); 3 çağrı yeri | logic.py, overlay.py |
| G61 | Negatif/sıfır adet/çarpan sessizce yutuluyor | `TargetSheet._num(positive=True)` → ≤0 `_INVALID`, kırmızı işaret | overlay.py |
| G62 | Twitter keyword istekleri sıralı (N×gecikme) | `_fetch_items` `ThreadPoolExecutor` ile paralel (max 6 worker), sıra korunur | twitter_client.py |
| G63 | Twitter poll hata sonrası backoff yok | ardışık hatada exponential backoff (60sn→15dk cap), başarıda sıfırlanır | overlay.py |
| G64 | TV auth token pozitif cache süresiz | `_invalidate_tv_auth_token`; fetch boş sonuçta bir kez invalide+retry | data_fetcher.py |
| G65 | sanitize_stocks inf/nan geçiriyor → 'inf' gösterimi | `math.isfinite` filtresi; `compute_pnl` inf entry/price'ta (None,None) | logic.py |
| G66 | Ölü kod: fetch_tv_rsi, TWITTER_BEARER_TOKEN | `fetch_tv_rsi` bulk retry sarmalayıcısına dönüştü; BEARER_TOKEN config'ten kaldırıldı | data_fetcher.py, config.py |
| G67 | twitter_client Nitter docstring atfı + ulaşılamayan return | docstring RSSHub'a güncellendi; ölü `last_err` return sadeleştirildi | twitter_client.py |
| G68 | test_overlay_ui import sıralaması (I001) | `ruff --fix` | tests/ |
| G69 | Test kapsamı boşlukları | +27 test: `_get_tv_auth_token`/invalidate, config sır uyarısı + Keychain dalları, `test_paths.py` (yeni), `is_valid_user_symbol`/sanitize/compute_pnl/tw_ago; 2 totolojik test gerçek fonksiyonu sürecek şekilde düzeltildi | tests/ |

## Doğrulama
- `python3 -m pytest -q` → **279 passed** (252 → 279, +27).
- `python3 -m ruff check .` → **All checks passed**.
- Bundle: `AAPL yf=AAPL, tv=NASDAQ:AAPL`, US_SYMBOLS 2081 NASDAQ.

## Bilinçli KAPSAM DIŞI (kullanıcı kararı — teknik borç)
- **overlay.py God-module (2883 satır)** — kalıcılık/UI/orkestrasyon iç içe.
- **`_rebuild_rows` O(n)** — her yapısal mutasyonda tüm widget'lar yeniden kurulur (düşük şiddet, veri kaybı yok).
- Kullanıcı "teknik borç kaydet, dokunma" seçti (yüksek regresyon riski). Refactor ertelendi.
