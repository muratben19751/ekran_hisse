---
source: oturum notu
retrieved: 2026-08-16
type: session_note
immutable: true
---

# x_watch Entegrasyonu — 2026-08-16

## Ne değişti

x_watch adlı ayrı proje (github.com/muratben19751/tweet) RSSHub-uyumlu bir uç yayınlıyor:

    https://twit.muratben.com/twitter/user/<handle>?showRetweets=0  →  RSS XML

Sözleşme twitter_client.py'nin RSSHub'dan beklediğiyle aynı:
- namespace'siz `<item>`, kökte `dc:` öneki
- `<link>` içinde `/status/<id>`
- RFC822 `<pubDate>` (hep GMT)
- `<title>` = tweet metni, `<dc:creator>` = @handle
- **ASLA 503 dönmez** — en kötü ihtimalle boş kanal + 200

x_watch, X aramasını anahtar kelimeyle yokluyor. `<handle>` yorumu:
- `all` veya `hepsi` → tüm akış (ÖNERİLEN, dakikada tek istek)
- izlenen bir kelime (ör. `ttkom`) → o kelimenin akışı
- tanınmayan handle → tüm akış (varsayılan fallback)

## Yapılan değişiklikler

### ~/.ekranhisse/notes_config.env
Oluşturuldu (daha önce yoktu). Eklendi:
```
RSSHUB_URL=https://twit.muratben.com
TWITTER_ACCOUNTS=all
```
Keychain'de bu anahtarlar yoktu → env dosyası kazanır.

### Doğrulama sonucu
```
err= None
tweet= 27
user= 22
{'id': '2089071289466036715', 'text': 'İyi yayınlar hocam. Ttkom bakabilir misiniz?',
 'created_at': '2026-08-16T19:26:23+00:00', 'author_id': 'bulleeenttt'}
```
TTKOM izleme listesinde mevcut → sembol süzgeci geçiyor.

## Bilinen tuzak — sembol süzgeci
twitter_client sembol süzgecini kendi tarafında uygular: izleme listesindeki
sembollerden en az biri tweet metninde kelime sınırıyla geçmiyorsa tweet atılır.
x_watch şu an `ttkom` kelimesini izliyor → EkranHisse izleme listesinde TTKOM
olmalı (mevcut: AKBNK, TTKOM, TCELL, EREGL).

## Mimari not
x_watch kendi RSSHub'ı; EkranHisse'nin self-hosted RSSHub'ı değil. İki servis:
- Eski: `config.RSSHUB_URL` → self-hosted RSSHub → X API (keyword/user-timeline)
- Yeni: `config.RSSHUB_URL=https://twit.muratben.com` → x_watch → X arama
twitter_client.py'de kod değişikliği yapılmadı; yalnızca yapılandırma değişti.
