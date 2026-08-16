---
title: twitter_client
type: entity
summary: 𝕏/Twitter ağ katmanı — 2026-08-16'dan beri x_watch (twit.muratben.com) köprüsü; TWITTER_ACCOUNTS=all ile tek istek/dakika. Kod değişmedi, yalnızca RSSHUB_URL+TWITTER_ACCOUNTS yapılandırması güncellendi.
sources:
  - sources/05_nitter_rss_2026-08-13.md
  - sources/07_oturum_2026-08-14.md
  - sources/11_rsshub_user_timeline_2026-08-14.md
  - sources/13_xwatch_entegrasyon_2026-08-16.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-16
---

# twitter_client

𝕏/Twitter erişimini UI'dan (overlay) ayıran **ağ katmanı**;
`notes_api_client` ile aynı callback deseni.

## API (değişmedi — sözleşme korundu)
- `fetch_recent(query, callback)` → `callback((tweets, users, err))`
  - `tweets`: `[{"id","text","created_at","author_id"}]` (`created_at` ISO8601)
  - `users`: `{author_id: {"username","name"}}`
- `fetch_ids(query, callback)` → `callback((ids_set, err))`

Sonuçlar `(data, err)` tuple deseniyle taşınır; hata yutulmaz — çağıran (overlay)
`err`'e göre `tw_poll_error` Signal'ini tetikler (bkz. bulgu G36).

## Veri kaynağı evrimi
1. **X API v2 `search/recent`** — ücretli oldu, kredi bitince **402** (bkz. [[known_issues]]).
2. **Nitter search RSS** (2026-08-13) — public instance ekosistemi çöktü (403/kapalı/anti-bot).
3. **RSSHub keyword route** (2026-08-13) — `config.RSSHUB_URL` self-hosted köprü.
4. **RSSHub user-timeline** (2026-08-14) — keyword route X tarafında bozuldu.
5. **x_watch (twit.muratben.com)** (2026-08-16, GÜNCEL) — ayrı proje, RSSHub-uyumlu uç, `TWITTER_ACCOUNTS=all`.

Her adımda **public API aynen korundu** → `overlay`/`logic`/testler sözleşmesi değişmedi.

## x_watch köprüsü (2026-08-16) — güncel
**Ne:** `github.com/muratben19751/tweet` projesi, `https://twit.muratben.com/twitter/user/<handle>?showRetweets=0`
adresinde RSSHub-uyumlu RSS XML yayınlıyor. Sözleşme twitter_client.py'nin beklediğiyle birebir aynı
(namespace'siz `<item>`, `dc:creator`, RFC822 `<pubDate>`). **ASLA 503 dönmez** — en kötü ihtimalle boş kanal + 200.

**Yapılandırma (`~/.ekranhisse/notes_config.env`):**
```
RSSHUB_URL=https://twit.muratben.com
TWITTER_ACCOUNTS=all
```
`all` handle'ı → x_watch tüm akışı döner (dakikada tek istek). Kod değişikliği yapılmadı.

**Doğrulama (2026-08-16):** `err=None`, 27 tweet, 22 kullanıcı — TTKOM izleme listesinde mevcut, süzgeç geçiyor.

## RSSHub user-timeline köprüsü (2026-08-14) — tarihsel
**Neden değişti:** RSSHub `keyword` (arama) route'u X tarafında bozuk. Canlı probe:
`/twitter/keyword/TTKOM` → **503**, RSSHub logu `Twitter API error: 404` (X arama
GraphQL endpoint'i 404). Token GEÇERLİ (`/twitter/user/elonmusk` → **200**); iki
token ve `diygod/rsshub:latest` ile de keyword bozuk. **user-timeline route çalışıyor.**

- `_DEFAULT_ACCOUNTS` — sabit finans/borsa handle listesi (`isyatirim`,
  `ziraatyatirim`, `oyakyatirim`, `fintables`, `borsagundem`). `_accounts()` önce
  `config.TWITTER_ACCOUNTS` (virgülle çoklu, `@` sıyrılır) doluysa onu kullanır.
- `_fetch_one(handle)` — `GET {base}/twitter/user/{handle}?showRetweets=0`
  (`showRetweets=0` eski `-is:retweet` niyetini korur). Gövde `body.lstrip()`
  sonrası ElementTree ile parse.
- `_fetch_items(query)` — hesapları **paralel** çeker (`ThreadPoolExecutor`, max 6);
  en az bir hesap başarılıysa kısmi sonuç döner (`err None`), hepsi düşerse son hata.
- `_symbols_from_query(query)` — X-stili sorgudan (`(THYAO OR AKBNK) lang:tr -is:retweet`)
  sembol terimlerini çıkarır: operatör/parantez/`OR` sıyrılır, büyük harf, yinelemesiz.
- `_matches_symbols(text_up, symbols)` — kelime sınırlı filtre
  `(?<![A-Z0-9])SYM(?![A-Z0-9])` (`logic._sym_regex` ile aynı mantık): `#SASA`,
  `$TCELL` eşleşir; `THYAOX` içindeki `THYAO` eşleşmez. `symbols` boşsa süzme yok.
- `fetch_recent`/`fetch_ids` gelen tüm timeline tweet'lerini bu filtreden geçirir →
  dedup (id) → `created_at` azalan sort. **fetch_ids de aynı filtreyi uygular**
  (aksi halde poll id'leri ile gösterilen tweet'ler uyuşmaz, okunmamış sayacı şişerdi).
- `_parse_item(item)` — `id` = `<link>`/`<guid>` içinden `/status/(\d+)`; `text` =
  `<title>` → `html.unescape`; `created_at` = `<pubDate>` (RFC822) → ISO8601.
  **author fallback**: `dc:creator` yoksa handle tweet link'inden
  (`(?:twitter|x)\.com/([^/]+)/status/`), görünen ad `<author>`'dan (user-timeline
  route `dc:creator` vermeyebiliyor).

## Hesap seçimi (ampirik gerçek)
RSSHub bazı hesapların **yıllar önceki cache'ini** veriyor → kullanılamaz:
`borsainsan`→2021, `hisseanalizi`→2017, `foreks_tr`→2016, `Matriksdata`→2014.
Seçim kriteri: (1) hâlâ aktif tweet atıyor (2026-08), (2) tweet'lerinde ticker
(`#SEMBOL`/`$SEMBOL`) geçiyor. Aracı kurum hesapları (bilanço/öneri) ve
`borsagundem` düzenli ticker kullanır; makro-haber hesapları (`bloomberght`,
`Ekonomim`) sembol filtresinden geçmez.

## Dayanıklılık
- **Çoklu hesap fallback**: biri hata/kapalı ise diğerleri sürer (paralel).
- HTTP **429**'da `Retry-After`'a saygı, `_MAX_BACKOFF=30`s sınırlı, `_MAX_RETRIES=2`.
- HTTP **503** → kullanıcı-dostu `"X oturumu geçersiz (RSSHub token'ı yenile)"`.
- Ağ çağrıları arka plan thread'inde; sonuç Signal ile ana thread'e geçer.
- overlay `_twitter_poll_apply`: hata sonrası ilk başarılı poll'de panel boşsa tam
  `_twitter_load` tetikler → panel tweet METNİYLE toparlanır (poll yalnız id taşır).

## RSSHub container
`docker run` ile (compose değil), tek env `TWITTER_AUTH_TOKEN` (X `auth_token`
cookie'si; EkranHisse'de saklanmaz), `--restart unless-stopped` (Mac reboot'unda
ayakta kalsın). `TWITTER_AUTH_TOKEN` virgülle çoklu verilebilir (rate-limit rotasyonu).

## Açık teknik borç (bkz. [[known_issues]])
- **Kapsam sınırı**: user-timeline, canlı keyword-search kadar zengin değil — yalnız
  seçili hesapların ticker geçen tweet'leri görünür. `config.TWITTER_ACCOUNTS`'a
  aktif ticker-hesabı eklenerek genişletilebilir.
- Sembol sayısı limitsiz (filtre client-tarafı; istek sayısı hesapla sabit, sembolle değil).

## İlgili
- [[overlay_window]]
- [[architecture_overview]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
- [[known_issues]]
- [[overlay_window]]
<!-- BACKLINKS:END -->
