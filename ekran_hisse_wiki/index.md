# NautilusTrader Wiki — İçerik Kataloğu

Bu sayfa `tools/wiki_tools.py index` tarafından her sayfanın frontmatter'ından yeniden üretilir. Elle düzenlemeyin.

## Kaynaklar (immutable)
- [[01_proje_ozet|01 Proje Ozet]]  (`sources/01_proje_ozet.md`)
- [[02_deepr_review_2026-08-11|02 Deepr Review 2026-08-11]]  (`sources/02_deepr_review_2026-08-11.md`)

## Entities (somut bileşenler)
- [[data_fetcher|DataFetcher]] — TradingView WebSocket üzerinden BIST fiyatı ve RSI çeken, yfinance bulk-fetch kullanan veri katmanı; auth token thread-safe cache, NaN/ZeroDivision ve falsy-zero koruması içerir.  (`wiki/entities/data_fetcher.md`)
- [[overlay_window|OverlayWindow]] — Ana pencere widget'ı; şeffaf macOS overlay olarak sağ kenarda açılır, hisse/Twitter/not sekmelerini barındırır; floating, monitör geçişi ve sürükleme destekler.  (`wiki/entities/overlay_window.md`)
- [[sparkline|Sparkline (Pseudo Heikin-Ashi)]] — StockRow içinde fiyat geçmişini pseudo Heikin-Ashi mumlarıyla gösteren mini grafik widget'ı.  (`wiki/entities/sparkline.md`)
- [[stock_row|StockRow]] — Tek bir hisseyi gösteren satır widget'ı; sembol, pseudo-HA sparkline, fiyat, değişim yüzdesi ve RSI etiketleri içerir.  (`wiki/entities/stock_row.md`)

## Synthesis (karşılaştırmalar & rehberler)
- [[architecture_overview|Mimari Genel Bakış]] — EkranHisse'nin katmanlı mimarisi: Qt overlay, TV WebSocket veri katmanı, signal köprüsü, floating/monitör yönetimi, uygulama paketi ve env-tabanlı sır yönetimi.  (`wiki/synthesis/architecture_overview.md`)
- [[known_issues|Bilinen Sorunlar]] — EkranHisse'de DeepR review ve canlı doğrulamayla tespit edilen açık bug'lar ve teknik borç; 2026-08-11 itibarıyla çözülen maddeler işaretli.  (`wiki/synthesis/known_issues.md`)
