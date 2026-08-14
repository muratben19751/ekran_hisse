---
title: twitter_client
type: entity
summary: 𝕏/Twitter ağ katmanı — 2026-08-13'ten beri X API v2 (402 credits depleted) yerine Nitter search RSS köprüsü; fetch_recent/fetch_ids aynı (data, err) callback şeklini korur, çoklu instance fallback + 429 backoff. Bearer token gerektirmez.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
  - sources/04_oturum_2026-08-13.md
  - sources/05_nitter_rss_2026-08-13.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-13
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

## Nitter RSS köprüsü (2026-08-13) — bearer'sız
X API v2 `search/recent` ücretli oldu ve hesap kredisi tükenince **402
"credits depleted"** döndürüyordu (bkz. [[known_issues]]). Kullanıcı ücretsiz
çözüm istedi; modülün **içi** Nitter search RSS'e çevrildi, **public API aynen
korundu** → `overlay`/`logic`/testler değişmedi.

- `_DEFAULT_INSTANCES` — kod içi fallback listesi. `_instances()` önce
  `config.NITTER_INSTANCES` (virgülle çoklu) doluysa onu kullanır.
- `_clean_query(query)` — X-özel operatörleri (`lang:`/`-is:`/`filter:`) regex ile
  sıyırır; parantez/`OR`/semboller kalır; sıyırma sonucu boşsa orijinali kullanır.
  (Nitter search bu operatörleri desteklemez.)
- `_fetch_rss(query)` — instance'ları **sırayla** dener:
  `GET {inst}/search/rss?f=tweets&q={quote(clean)}` (timeout 10). Başarılı gövde
  `body.lstrip()` sonrası `xml.etree.ElementTree` ile parse edilir (bazı instance'lar
  XML öncesi boşluk ekliyor). Tümü düşerse `(None, "kaynak yok")`.
- `_parse_item(item)` — `id` = `<link>`/`<guid>` içinden `/status/(\d+)`; `text` =
  `<title>` → `html.unescape`; `created_at` = `<pubDate>` (RFC822) →
  `email.utils.parsedate_to_datetime().isoformat()`; `author_id` = username
  (Nitter'da numeric id yok); user = `<dc:creator>` (`@handle`).

## Dayanıklılık
- **Çoklu instance fallback**: biri hata/kapalı ise sıradaki denenir.
- HTTP **429**'da `Retry-After`'a saygı gösterir, `_MAX_BACKOFF=30`s ile sınırlı,
  `_MAX_RETRIES=2` — sonra sıradaki instance.
- Ağ çağrıları arka plan thread'inde; sonuç Signal ile ana thread'e geçer.

## ⚠️ Canlı durum: public instance'lar kapalı (2026-08-13)
Canlı probe'da **hiçbir public Nitter instance'ı anonim RSS vermiyor**:
nitter.net 403, privacydev kapalı, poast/tiekoetter bot-challenge, xcancel
whitelist gerektiriyor. Köprü kodu doğru çalışıyor (402 gitti, fallback döngüsü
instance sırasını dolaşıyor) ama **veri akışı instance sağlığına bağlı** — bugün
boş gelir. Güvenilir ücretsiz yol: **kendi Nitter instance'ını** (Docker + guest
token) kurup `NITTER_INSTANCES`'a eklemek. Bkz. [[known_issues]].

## Açık teknik borç (bkz. [[known_issues]])
- Sembol sayısı limitsiz; ~40+ sembolde sorgu çok uzayabilir.
- `lang:tr` Nitter search'te uygulanmaz → Türkçe-dışı sonuç gelebilir (ileride
  client-tarafı dil filtresi düşünülebilir).

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
