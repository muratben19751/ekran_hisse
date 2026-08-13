# NautilusTrader Wiki — İçerik Kataloğu

Bu sayfa `tools/wiki_tools.py index` tarafından her sayfanın frontmatter'ından yeniden üretilir. Elle düzenlemeyin.

## Kaynaklar (immutable)
- [[01_proje_ozet|01 Proje Ozet]]  (`sources/01_proje_ozet.md`)
- [[02_deepr_review_2026-08-11|02 Deepr Review 2026-08-11]]  (`sources/02_deepr_review_2026-08-11.md`)
- [[03_deepr_review_round2_2026-08-12|03 Deepr Review Round2 2026-08-12]]  (`sources/03_deepr_review_round2_2026-08-12.md`)
- [[04_oturum_2026-08-13|04 Oturum 2026-08-13]]  (`sources/04_oturum_2026-08-13.md`)
- [[05_nitter_rss_2026-08-13|05 Nitter Rss 2026-08-13]]  (`sources/05_nitter_rss_2026-08-13.md`)
- [[06_reorder_pnl_2026-08-13|06 Reorder Pnl 2026-08-13]]  (`sources/06_reorder_pnl_2026-08-13.md`)

## Entities (somut bileşenler)
- [[data_fetcher|DataFetcher]] — TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance bulk-fetch kullanan veri katmanı; auth token thread-safe cache, NaN/ZeroDivision ve falsy-zero koruması içerir.  (`wiki/entities/data_fetcher.md`)
- [[overlay_window|OverlayWindow]] — Ana pencere widget'ı; şeffaf macOS overlay olarak sağ-alta yaslı açılır, hisse/Twitter/not sekmelerini barındırır; floating, monitör geçişi, sürükleme, kenar/köşe boyutlandırma ve font ölçekleme destekler.  (`wiki/entities/overlay_window.md`)
- [[paths|paths]] — EkranHisse'nin veri-dizini yol politikasının tek kaynağı — ~/.ekranhisse için DATA_DIR, ensure_data_dir() ve data_file(); OSError'da ~'a fallback.  (`wiki/entities/paths.md`)
- [[sparkline|Sparkline (Pseudo Heikin-Ashi)]] — StockRow içinde fiyat geçmişini pseudo Heikin-Ashi mumlarıyla gösteren mini grafik widget'ı.  (`wiki/entities/sparkline.md`)
- [[stock_row|StockRow]] — Tek bir hisseyi gösteren satır widget'ı; sembol, pseudo-HA sparkline, fiyat, %değişim, kâr/zarar (tutar & %) ve RSI etiketleri; sağ-tık menüsünden hedef/adet, taşıma ve kaldırma.  (`wiki/entities/stock_row.md`)
- [[symbols|symbols]] — Sembol evreninin tek kaynağı — symbols.json'dan BIST_SYMBOLS/SPECIALS/KNOWN; fiyat (yfinance) ve RSI (TradingView) ticker eşlemesi tek yerde. 2026-08-13'ten beri ekleme is_known ile kısıtlı DEĞİL — her geçerli biçimdeki sembol eklenip varsayılan eşlemeyle çekilebilir.  (`wiki/entities/symbols.md`)
- [[twitter_client|twitter_client]] — 𝕏/Twitter ağ katmanı — 2026-08-13'ten beri X API v2 (402 credits depleted) yerine Nitter search RSS köprüsü; fetch_recent/fetch_ids aynı (data, err) callback şeklini korur, çoklu instance fallback + 429 backoff. Bearer token gerektirmez.  (`wiki/entities/twitter_client.md`)

## Synthesis (karşılaştırmalar & rehberler)
- [[architecture_overview|Mimari Genel Bakış]] — EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, paths/symbols/twitter_client/applog modülleri, floating/monitör yönetimi ve Keychain-öncelikli sır yönetimi.  (`wiki/synthesis/architecture_overview.md`)
- [[known_issues|Bilinen Sorunlar]] — EkranHisse'de üç DeepR review turuyla (2026-08-06/11/12) tespit edilen bug'lar + teknik borç; ayrıca 2026-08-13 tweet alarmı X API 402'den Nitter RSS köprüsüne taşındı (bearer'sız), kalan engel public Nitter instance'larının kapalı olması.  (`wiki/synthesis/known_issues.md`)
