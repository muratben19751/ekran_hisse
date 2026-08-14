# NautilusTrader Wiki — İçerik Kataloğu

Bu sayfa `tools/wiki_tools.py index` tarafından her sayfanın frontmatter'ından yeniden üretilir. Elle düzenlemeyin.

## Kaynaklar (immutable)
- [[01_proje_ozet|01 Proje Ozet]]  (`sources/01_proje_ozet.md`)
- [[02_deepr_review_2026-08-11|02 Deepr Review 2026-08-11]]  (`sources/02_deepr_review_2026-08-11.md`)
- [[03_deepr_review_round2_2026-08-12|03 Deepr Review Round2 2026-08-12]]  (`sources/03_deepr_review_round2_2026-08-12.md`)
- [[04_oturum_2026-08-13|04 Oturum 2026-08-13]]  (`sources/04_oturum_2026-08-13.md`)
- [[05_nitter_rss_2026-08-13|05 Nitter Rss 2026-08-13]]  (`sources/05_nitter_rss_2026-08-13.md`)
- [[06_reorder_pnl_2026-08-13|06 Reorder Pnl 2026-08-13]]  (`sources/06_reorder_pnl_2026-08-13.md`)
- [[07_oturum_2026-08-14|07 Oturum 2026-08-14]]  (`sources/07_oturum_2026-08-14.md`)
- [[08_deepr_review_round4_2026-08-14|08 Deepr Review Round4 2026-08-14]]  (`sources/08_deepr_review_round4_2026-08-14.md`)
- [[09_sparkline_intraday_2026-08-14|09 Sparkline Intraday 2026-08-14]]  (`sources/09_sparkline_intraday_2026-08-14.md`)
- [[10_dikey_resize_fix_2026-08-14|10 Dikey Resize Fix 2026-08-14]]  (`sources/10_dikey_resize_fix_2026-08-14.md`)
- [[11_rsshub_user_timeline_2026-08-14|11 Rsshub User Timeline 2026-08-14]]  (`sources/11_rsshub_user_timeline_2026-08-14.md`)
- [[12_tv_seri_limiti_sirali_akis_2026-08-14|12 Tv Seri Limiti Sirali Akis 2026-08-14]]  (`sources/12_tv_seri_limiti_sirali_akis_2026-08-14.md`)

## Entities (somut bileşenler)
- [[data_fetcher|DataFetcher]] — TradingView WebSocket üzerinden BIST + ABD (NYSE/NASDAQ) fiyatı, RSI ve sparkline intraday bar serisi çeken veri katmanı; TV hesap seri kotası düşük olduğundan RSI/history serileri tek WS'te SIRALI akıtılır (_stream_tv_series), yfinance bulk (FX/altın/kripto), auth token thread-safe cache + boş-sonuçta invalidasyon, NaN/falsy-zero/tam-sembol koruması.  (`wiki/entities/data_fetcher.md`)
- [[overlay_window|OverlayWindow]] — Ana pencere widget'ı; şeffaf macOS overlay olarak sağ-alta yaslı açılır, hisse/Twitter/not sekmelerini barındırır; floating, monitör geçişi, sürükleme, kenar/köşe boyutlandırma ve font ölçekleme destekler.  (`wiki/entities/overlay_window.md`)
- [[paths|paths]] — EkranHisse'nin veri-dizini yol politikasının tek kaynağı — ~/.ekranhisse için DATA_DIR, ensure_data_dir() ve data_file(); OSError'da ~'a fallback.  (`wiki/entities/paths.md`)
- [[sparkline|Sparkline (Çizgi + Alan Dolgusu)]] — StockRow içinde gün-içi fiyatı GERÇEK intraday bar serisiyle (TV 5dk × 24 = son ~2 saat) çizgi + degrade alan dolgusu olarak gösteren mini grafik; canlı fiyat son barı günceller, son nokta anlık fiyatı vurgular.  (`wiki/entities/sparkline.md`)
- [[stock_row|StockRow]] — Tek bir hisseyi gösteren satır widget'ı; sembol + çizgi sparkline (gerçek intraday) + fiyat + yüzde-pill'i ana satırda, kâr/zarar (tutar & %) ve RSI alttaki meta satırında; sağ-tık menüsünden hedef/adet/çarpan, taşıma ve kaldırma.  (`wiki/entities/stock_row.md`)
- [[symbols|symbols]] — Sembol evreninin tek kaynağı — symbols.json'dan BIST_SYMBOLS/SPECIALS/US_SYMBOLS/KNOWN; fiyat (yfinance) ve RSI (TradingView) ticker eşlemesi tek yerde. 2026-08-14'ten beri ABD hisseleri (NYSE/NASDAQ) desteklenir; çözümleme SPECIALS→BIST→US→fallback önceliğiyle.  (`wiki/entities/symbols.md`)
- [[twitter_client|twitter_client]] — 𝕏/Twitter ağ katmanı — 2026-08-14'ten beri RSSHub user-timeline köprüsü (keyword/arama route'u X tarafında bozuldu: 404→503). Sabit finans hesaplarının timeline'ları çekilir, izlenen sembollere göre süzülür; fetch_recent/fetch_ids (data,err) callback şekli korunur.  (`wiki/entities/twitter_client.md`)

## Synthesis (karşılaştırmalar & rehberler)
- [[architecture_overview|Mimari Genel Bakış]] — EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, paths/symbols/twitter_client/applog modülleri, floating/monitör yönetimi ve Keychain-öncelikli sır yönetimi.  (`wiki/synthesis/architecture_overview.md`)
- [[known_issues|Bilinen Sorunlar]] — EkranHisse'de dört DeepR review turuyla (2026-08-06/11/12/14) tespit edilen bug'lar + teknik borç. 4. tur (2026-08-14) 28 doğrulanmış bulgunun tümü düzeltildi (mimari refactor hariç); kritik veri-kaybı yolları (stocks.json bozuk-dosya + not silme onayı) kapatıldı, .app bundle US eşlemesi senkronlandı.  (`wiki/synthesis/known_issues.md`)
