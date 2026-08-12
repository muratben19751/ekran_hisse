---
title: twitter_client
type: entity
summary: 𝕏/Twitter v2 API ağ katmanı — UI'dan ayrık; fetch_recent/fetch_ids callback ile (data, err) döndürür, HTTP 429'da Retry-After'a saygı gösterip sınırlı yeniden dener.
sources:
  - sources/03_deepr_review_round2_2026-08-12.md
related:
  - wiki/synthesis/architecture_overview.md
last_updated: 2026-08-12
---

# twitter_client

𝕏/Twitter erişimini UI'dan (overlay) ayıran **ağ katmanı**;
`notes_api_client` ile aynı callback deseni. DeepR bulgusu G55 kapsamında
rate-limit dayanıklılığı eklendi.

## API
- `fetch_recent(query, callback)` → `callback((tweets, users, err))`
- `fetch_ids(query, callback)` → `callback((ids_set, err))`

Sonuçlar `(data, err)` tuple deseniyle taşınır; hata yutulmaz — çağıran (overlay)
`err`'e göre `tw_poll_error` Signal'ini tetikleyebilir (bkz. bulgu G36).

## Dayanıklılık
- HTTP **429**'da `Retry-After` header'ına saygı gösterir ve **sınırlı** yeniden
  deneme yapar (sonsuz döngü yok).
- Ağ çağrıları arka plan thread'inde; sonuç Signal ile ana thread'e geçer.

## Açık teknik borç (bkz. [[known_issues]])
- Sembol sayısı limitsiz; ~40+ sembolde 512 byte sorgu limitini aşabilir.
- `TWITTER_QUERY` env'de tanımlı ama okunmuyor olabilir (doğrulanmalı).

## İlgili
- [[overlay_window]]
- [[architecture_overview]]
- [[known_issues]]

<!-- BACKLINKS:BEGIN -->
## Referenced by

- [[architecture_overview]]
<!-- BACKLINKS:END -->
