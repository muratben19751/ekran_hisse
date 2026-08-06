# ekran_hisse Wiki — Schema (CLAUDE.md)

Bu wiki, Karpathy'nin **"LLM Knowledge Base / LLM Wiki Pattern"** yaklaşımına göre kurulmuştur (bkz. https://karpathy.bearblog.dev/llm-knowledge-bases/ ve https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Amaç: **ekran_hisse** projesi hakkında bilinen her şeyi, bir LLM ajanının **hem okuyabileceği hem de bakımını yapabileceği** düz-metin bir bilgi tabanında canlı tutmak. Kullanıcı wiki'yi doğrudan düzenlemez — sorular sorar, çıktılar üretir, boşlukları raporlar; LLM sayfaları yazar/günceller.

> **İlk senkron notu (LLM için):** Bu şema bootstrap ile üretildi. İlk `wiki-sync`
> geçişinde bu dosyayı projeye göre özelleştir: yukarıdaki "Amaç" cümlesini projenin
> gerçek konusuyla netleştir ve aşağıdaki **Konu Sınırları (Scope)** bölümünü projeye
> özgü doldur. Katmanlı yapı, frontmatter ve adlandırma kuralları genel kalır.

## Katmanlı Yapı

```
ekran_hisse_wiki/
├── CLAUDE.md              # Schema — bu dosya
├── index.md               # Kategorik katalog (üretilen, elle düzenlenmez)
├── log.md                 # Append-only işlem günlüğü
├── sources/               # Katman 1 — Ham, değiştirilmez kaynak snapshot'ları
├── wiki/                  # Katman 2 — LLM'in sahibi olduğu sentezlenmiş sayfalar
│   ├── entities/          # Somut şeyler: bileşenler, modüller, veri kaynakları
│   ├── concepts/          # Soyut fikirler: mimari desenler, iş akışları
│   ├── synthesis/         # Sentez: karşılaştırmalar, tavsiyeler, rehberler
│   └── tutorials/         # Öğreticilerin/kılavuzların sentezleri
├── lint/                  # Health-check raporları (YYYY-MM-DD_health.md)
├── tools/                 # wiki_tools.py — CLI: index, backlinks, lint, search, stub, resolve
└── .obsidian/             # (opsiyonel) Obsidian workspace — frontend olarak kullanılabilir
```

### Katman 1 — `sources/`
- **Sadece okunur.** LLM asla düzenlemez.
- Her dosya frontmatter içermeli: `source`, `retrieved`, `type`, `immutable: true`.
- URL değişse bile içerik korunur; yeni sürüm ayrı dosya olarak eklenir (`05_...`).

### Katman 2 — `wiki/`
- LLM tam sahibidir.
- **Zorunlu frontmatter:** `title`, `type`, `summary`, `sources`, `last_updated`.
- **Opsiyonel:** `status: stub | draft | frozen`, `key_concepts`.
- Sayfalar arası bağ **bare-name wikilink** biçiminde: `[[core_module]]`, `[[core_module|Çekirdek Modül]]`. Path'li `[[wiki/entities/core_module.md]]` deprecated — `tools/wiki_tools.py backlinks` her ikisini de kabul eder ama yeni sayfalarda bare form kullanılır.

### Katman 3 — Bu dosya (`CLAUDE.md`)
- Şemayı, adlandırma kurallarını ve iş akışlarını tanımlar.

## Frontmatter Referansı

```yaml
---
title: CoreModule                             # Human-friendly
type: entity                                  # entity | concept | synthesis | tutorial
summary: >-                                   # 1 cümle, <=180 karakter — index.md için
  Projenin çekirdek modülü; şu sorumluluğu taşır ...
status: draft                                 # opsiyonel: stub | draft | frozen
key_concepts:                                 # opsiyonel: bare-name slug listesi
  - event_driven_architecture
sources:                                      # ZORUNLU — Layer 1 anchor'lar (sources/*.md veya URL)
  - sources/01_readme.md
related:                                       # opsiyonel — Layer 2 wiki cross-reference'ları
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-01-01
---
```

- **`summary` alanı zorunlu.** `tools/wiki_tools.py index` katalog satırlarını buradan üretir; boşsa sayfa katalogda kısa görünür.
- **`sources` her zaman Layer 1 kaynak izlenebilirliği içindir.** Yalnızca `sources/*.md` snapshot dosyaları ve URL'ler kabul edilir. Wiki sayfası başka bir wiki sayfasını kaynak olarak gösteremez — o Layer 2 türetmedir.
- **`related` opsiyoneldir**; sayfanın kavramsal komşusu olan wiki sayfalarına referanslar burada tutulur. `sources` ile karıştırılmaz.

## Adlandırma Kuralları

- `entities/` — `snake_case` isimler: `core_module.md`, `api_client.md`
- `concepts/` — Kısa fikir adı: `event_driven_architecture.md`, `caching_strategy.md`
- `synthesis/` — Açıklayıcı başlık: `architecture_overview.md`, `module_map.md`
- `tutorials/` — `tutorial_<slug>.md`
- **Bare slug'lar globalde eşsiz olmalı** — wikilink çözümlemesi stem üzerinden yapılıyor. Yeni sayfada mevcut bir stem'i tekrar kullanma.

## Backlinks

- Her `wiki/` sayfasının sonunda otomatik oluşturulan bir bölüm bulunur:

  ```
  <!-- BACKLINKS:BEGIN -->
  ## Referenced by
  - [[architecture_overview]]
  <!-- BACKLINKS:END -->
  ```
- Bu bölüm `tools/wiki_tools.py backlinks` çağrısı ile idempotent şekilde yeniden yazılır. **Elle düzenlemeyin.** Yeni sayfa eklendikten sonra veya wikilink değişiminde bu komutu çalıştırın.

## Temel Operasyonlar

### Ingest (Yeni kaynak ekleme)
1. Kaynağı `sources/NN_slug.md` olarak indir, frontmatter ile.
2. Yeni fikir/varlıkları çıkar → ilgili wiki sayfalarını güncelle veya `tools/wiki_tools.py stub <slug> <kind> "Title"` ile stub oluştur.
3. Her sayfanın `summary`, `sources`, `last_updated` alanlarını yenile.
4. `python tools/wiki_tools.py backlinks && python tools/wiki_tools.py index` çalıştır.
5. Çelişkiler + yeni gap'ler `log.md`'ye append.

### Query (Sorgu)
1. `python tools/wiki_tools.py search "query"` ile kaba sıralama al.
2. `python tools/wiki_tools.py show <slug>` veya `resolve <slug>` ile sayfaya git.
3. Cevapta citation kullan (`(kaynak: sources/01_readme.md)`).
4. Yeterince değerli sentezleri `synthesis/`'e yeni sayfa olarak dosyala; `summary` ve `sources` doldur; backlinks/index tazele.

### Lint (Periyodik sağlık kontrolü)
- `python tools/wiki_tools.py lint` → konsol raporu (broken_links, orphans, missing_summary, missing_frontmatter, stubs).
- `python tools/wiki_tools.py lint --write --date=YYYY-MM-DD` → `lint/YYYY-MM-DD_health.md` yazar.

### Stub (Bilinmezi işaretle)
- `python tools/wiki_tools.py stub core_module entity "CoreModule"` → boş iskelet.
- Stub sayfaları `status: stub` frontmatter'ıyla üretilir; `index.md`'de `*(stub)*` badge'i ile görünür.

### Frontend
- **Obsidian**: `ekran_hisse_wiki/` klasörünü Obsidian vault olarak aç. Bare-name wikilinks, graph view, backlinks paneli native çalışır (`newLinkFormat: shortest`, `useMarkdownLinks: false`).

## Konu Sınırları (Scope)

Bu wiki **EkranHisse** projesinin kendisi hakkındadır: macOS BIST hisse overlay uygulaması.
Kapsam: PySide6 UI mimarisi, TradingView WebSocket veri katmanı, sparkline/grafik bileşenleri,
uygulama paketi yapısı, Twitter/X ve not paneli entegrasyonları. Genel PySide6/Python teorisi
veya BIST piyasa bilgisi kapsam dışıdır.

## Sürüm Notu

Sürüme özgü iddialar ilgili sürüm etiketiyle işaretlenmelidir. `sources/` içindeki `retrieved` tarihi 180 günden eskise sayfa `status: stale` olarak `lint` tarafından işaretlenir.
