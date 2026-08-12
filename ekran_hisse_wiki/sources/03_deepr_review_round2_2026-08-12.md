---
source: "EkranHisse — DeepR 2. tur incelemesi + adversarial doğrulama (Claude Code oturumu, 2026-08-12)"
retrieved: 2026-08-12
type: review_log
immutable: true
---

# DeepR 2. Tur İnceleme + Adversarial Doğrulama — 2026-08-12

`sources/02_deepr_review_2026-08-11.md`'nin devamı. O tur (commit `b802327`/
`d8de974`) 33 fix kapatmıştı; bu tur onların ÜZERİNE yeni bir 11-boyut DeepR
çalıştırdı → **22 yeni bulgu**, tamamı düzeltildi ve adversarial doğrulamadan
geçti. Commit `e54430b`.

## Metodoloji
- 11-boyut paralel ajan (Performans, Mimari, Code, Brutal, End-User Neg/Poz,
  Edge Case, Entegrasyon, Statik/Lint, E2E, Unit) → her bulgu için çürütücü ajan.
- Doğrulama ayrı Workflow: her fix'e bir skeptik ajan (`fixed`/`refuted`).

## 22 bulgu (tamamı düzeltildi)

| # | Bulgu | Düzeltme |
|---|-------|----------|
| 22 | Sheet dialog açılınca panel modal-kör kapanıyordu | `_modal_open()` guard (4 kapanma yolu) + test |
| 23 | TV WS NaN fiyat → sparkline paint çökmesi | `data_fetcher` isnan filtresi + `Sparkline.push` NaN/None guard |
| 24 | Twitter poll hatası yutuluyordu | `tw_poll_error` Signal + status/log |
| 25 | Fiyat var ama `change_pct` None ise sparkline güncellenmiyordu | `push` koşulsuz (if/else dışına) |
| 26 | Hedef girişi geçersiz sayıda sessizce None kaydediyordu | `_INVALID` sentinel + kırmızı kenar + accept reddi |
| 27 | Silinip yeniden eklenen hisse bayat fiyat | `_last_data.pop(symbol)` |
| 28 | Floating modda monitör değişince panel görünmez | `_reposition_to_screen` genişlik senkronu |
| 29 | 𝕏 chip sayaçları çakışan sembollerde yanıltıcı | `symbols_of_tweet` (çok-sembol) |
| 30 | RSI worker `_rsi_fetching`'i ana thread dışından yazıyor | `rsi_done` Signal + `_on_rsi_done` (emit try/finally içinde) |
| 31 | `~/.ekranhisse` üç modülde bağımsız hardcode | yeni `paths.py` (tek kaynak) |
| 32 | WS `run_forever` thread'i sızabilir | `ping_interval`/`ping_timeout` + `setdefaulttimeout` |
| 33 | TV auth token negatif sonucu cache'lenmiyor | negatif TTL cache (60 sn) |
| 34 | `_calc_rsi` warm-up bar yetersiz (24) | `_RSI_WARMUP_BARS = 150` |
| 35 | import anında sır snapshot — kurulum sırası hatası | setup.command blocking `read` + Keychain recheck |
| 36 | `save_notes` latest-wins çok cihazda not eziyor | **yalnız belgeleme** (docstring + doküman); merge kapsam dışı |
| 37 | Doküman "Hedef rozeti"+"track" UI'da yok; `C_TRACK` ölü sabit | doküman gerçeğe çekildi + ölü sabit silindi |
| 38 | `StockRow.update_rsi` test edilmemiş | eşik-renk + NaN + anchor testleri |
| 39 | `_add_from_search`/`is_known` doğrulama test edilmemiş | bilinmeyen/boş/tekrar sembol testleri |
| 40 | `apply_rsi` cache + rebuild köprüsü test edilmemiş | cache/restore testi |
| 41 | Sheet-panel etkileşim test kapsamı yok | `test_modal_open_guards_outside_click_close` |
| — | (ek) RSI `rsi_done.emit()` try/finally'de değildi | emit döngüsü dış try'da; bayrak her yolda sıfırlanır |

## Doğrulama sonuçları
- 22 fix adversarial: `unfixed_count: 0` — hiçbiri çürütülmedi. 16/22 temiz;
  6 ajan refutasyon ÜRETMEDEN teknik hatayla öldü (5× "Connection closed", 1×
  StructuredOutput cap).
- Ek tur (RSI try/finally + ölen 6 bulgu yeniden): **6/6 CONFIRMED**, 0 refuted.
- 1. tur resume doğrulaması: `test_save_notes_concurrent_latest_wins` flaky idi
  (impl yalnız *eventual* latest-wins garantiler) → 3000-run stress ile kanıtlandı,
  test garantili kontrata daraltıldı.

## Yeni modüller (bu tur + öncesi ayrıştırma)
- **`paths.py`** — `~/.ekranhisse` yol politikası tek kaynak (`DATA_DIR`,
  `ensure_data_dir`, `data_file`).
- **`twitter_client.py`** — 𝕏 API ağ katmanı (UI'dan ayrık; 429 Retry-After +
  sınırlı yeniden deneme; `fetch_recent`/`fetch_ids` → `(data, err)`).
- **`symbols.py`** — sembol evreni tek kaynak (`symbols.json`'dan `BIST_SYMBOLS`/
  `SPECIALS`/`KNOWN`; fiyat=yfinance & RSI=TradingView eşlemesi tek yerde).
- **`applog.py`** — merkezî logger (konsol + `~/Library/Logs/EkranHisse.log`).

## Güvenlik (kod gerçeği)
- Sırlar öncelikle macOS Keychain'den okunur (`config._keychain_get`); Keychain'de
  yoksa `~/.ekranhisse/notes_config.env` düz-metin **geçiş** fallback'i devrede,
  düz-metinde bulunursa bir kez uyarı verilir. Bundle'da sır tutulmaz. Sabitler
  import anında bir kez okunur (snapshot).
- Geçmişte sızmış tokenlar kullanıcı tarafından rotate edilmeli (advisory).

## Kalite kapısı
- Test 191→200. ruff (F,E,W,I; E501/E741 ignore) "All checks passed", pyflakes temiz.
- `pyproject.toml` + `dev-requirements.txt` eklendi (ruff/pytest yapılandırması).
- `stocks.json` (kullanıcı verisi) ve `notes_api.php`/`test.php` (eski PHP backend)
  repo'dan kaldırıldı + `.gitignore`.
