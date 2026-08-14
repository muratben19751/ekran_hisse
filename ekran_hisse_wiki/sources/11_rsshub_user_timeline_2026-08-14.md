---
source: EkranHisse oturum notu — RSSHub user-timeline geçişi
retrieved: 2026-08-14
type: session
immutable: true
---

# Tweet akışı: RSSHub keyword route çöktü → user-timeline köprüsü (2026-08-14)

## Belirti
𝕏 sekmesinde tweet paneli boş; durum etiketi "hata 503". Poll her 60sn'de
başarısız, alarm rozeti dolmuyor.

## Teşhis (canlı probe)
- RSSHub container ayakta: `docker ps` → `Up`, port `1200` açık.
- `curl localhost:1200/twitter/keyword/TTKOM` → **HTTP 503**.
- RSSHub logu: `twitter gql-id-resolver: fetching fresh query IDs` →
  `Error: Twitter API error: 404` → dışarıya `503`.
- `TWITTER_AUTH_TOKEN` GEÇERLİ: `curl .../twitter/user/elonmusk` → **HTTP 200**.
- İki farklı token'la ve `diygod/rsshub:latest` (2026-08-12 imaj) ile de keyword
  hâlâ 503.

**Kök neden:** RSSHub `keyword` (arama) route'u X tarafında bozuk — X'in arama
GraphQL endpoint'i `404` dönüyor. Token ölümü değil, route bozukluğu.
`user-timeline` route'u (`/twitter/user/<handle>`) çalışıyor (200).

## Çözüm — user-timeline modeli
`twitter_client` içi keyword-search'ten **user-timeline**'a çevrildi; public API
(`fetch_recent`/`fetch_ids` + callback) aynen korundu → overlay/logic değişmedi.

- `_DEFAULT_ACCOUNTS` — sabit finans/borsa handle listesi; `config.TWITTER_ACCOUNTS`
  (virgülle) doluysa onu kullanır. Her hesap `/twitter/user/<handle>?showRetweets=0`
  ile PARALEL çekilir (ThreadPoolExecutor, max 6).
- `_symbols_from_query(query)` — X-stili sorgudan sembol terimlerini çıkarır
  (operatör/paranteZ/OR sıyrılır, büyük harf, yinelemesiz).
- `_matches_symbols(text_up, symbols)` — kelime sınırıyla filtre
  `(?<![A-Z0-9])SYM(?![A-Z0-9])`; `#SASA`/`$TCELL` doğru eşleşir, `THYAOX` eşleşmez.
  symbols boşsa filtre uygulanmaz.
- `fetch_recent`/`fetch_ids` gelen tweet'leri bu filtreden geçirir → dedup → sort.
- `_parse_item` author fallback: user-timeline `dc:creator` vermeyebilir →
  handle tweet link'inden (`(?:twitter|x)\.com/([^/]+)/status/`), görünen ad
  `<author>`'dan.
- HTTP 503 → kullanıcı-dostu mesaj "X oturumu geçersiz (RSSHub token'ı yenile)".

## Hesap seçimi (ampirik)
RSSHub bazı hesapların YILLAR ÖNCEKİ cache'ini veriyor (kullanılamaz):
`borsainsan`→2021, `hisseanalizi`→2017, `foreks_tr`→2016, `Matriksdata`→2014.
Güncel (2026-08) + ticker (#SEMBOL/$SEMBOL) içeren hesaplar seçildi:
`isyatirim` (5/18 ticker-eşleşen), `ziraatyatirim` (2/19), `oyakyatirim`,
`fintables` (1/20, `$TCELL`), `borsagundem`. Makro-haber hesapları
(`bloomberght`, `Ekonomim`, `halktvcomtr`) ticker konuşmadığı için filtreden geçmez.

## overlay tarafı — otomatik toparlanma
`_twitter_poll_apply`: hata sonrası ilk başarılı poll'de panel boşsa
(`not self._tw_tweets`) tam `_twitter_load` tetiklenir → panel tweet METNİYLE
toparlanır (poll yalnız id taşır, metin taşımaz).

## RSSHub container (docker run, compose değil)
```
docker run -d --name rsshub --restart unless-stopped -p 1200:1200 \
  -e TWITTER_AUTH_TOKEN='<auth_token cookie>' -e NODE_ENV=production diygod/rsshub
```
`--restart unless-stopped` eklendi (eskisi `restart: no` idi → Mac reboot'unda ölüyordu).

## Sınırlama
user-timeline, canlı keyword-search kadar zengin değil — yalnız bu hesapların
ticker geçen tweet'leri görünür. Kapsam için `config.TWITTER_ACCOUNTS`'a
ticker-yoğun aktif hesap eklenebilir.

## Test
`tests/test_twitter_client.py` user-timeline modeline yeniden yazıldı (26 test):
sembol filtresi, kelime sınırı, author fallback, çoklu hesap dedup/sort/partial,
503→token ipucu, config override. Tüm suite 292 passed, ruff temiz.
