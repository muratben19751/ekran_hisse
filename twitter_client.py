"""EkranHisse — Twitter/X istemcisi (Nitter RSS köprüsü, ağ katmanı).

X API v2 `search/recent` artık ücretli ve hesap kredisi tükendiğinde HTTP 402
döndürüyor. Bu modül, aynı public arayüzü koruyarak veriyi **Nitter search RSS**
üzerinden ücretsiz çeker (bearer token gerekmez). overlay/logic ve callback
sözleşmesi değişmez:

fetch_recent(query, callback)  → callback((tweets, users, err))
fetch_ids(query, callback)     → callback((ids_set, err))

tweets: [{"id","text","created_at","author_id"}]  (created_at ISO8601)
users:  {author_id: {"username","name"}}

Nitter instance'ları kararsız olabilir; birden çok instance sırayla denenir
(config.NITTER_INSTANCES ile özelleştirilebilir). HTTP 429'da Retry-After'a
saygı gösterilir, sonra sıradaki instance'a geçilir.
"""

import html
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import config
from applog import log

# Bilinen public Nitter instance'ları (kod içi fallback). config.NITTER_INSTANCES
# doluysa o kullanılır. Instance'lar sık kapanabilir; kullanıcı çalışan birini
# NITTER_INSTANCES'a ekleyebilir.
_DEFAULT_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://xcancel.com",
]

_MAX_RETRIES = 2          # bir instance'ta 429 sonrası en fazla bu kadar tekrar
_MAX_BACKOFF = 30         # Retry-After'ı bu saniyeyle sınırla (UI'yı kilitleme)
_TIMEOUT = 10

# X-özel arama operatörleri (Nitter yok sayar/anlamaz) — köprüde sıyır.
_X_OPERATOR_RE = re.compile(r"(?:^|\s)-?(?:lang|is|filter):\S+", re.IGNORECASE)
_STATUS_ID_RE = re.compile(r"/status/(\d+)")


def _instances():
    """config.NITTER_INSTANCES (virgülle çoklu) doluysa onu, yoksa varsayılanı."""
    raw = (config.NITTER_INSTANCES or "").strip()
    if raw:
        insts = [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
        if insts:
            return insts
    return _DEFAULT_INSTANCES


def _clean_query(query):
    """X-özel operatörleri (lang:/is:/filter:) sıyır; arama terimlerini bırak.

    Nitter search bu operatörleri desteklemez; parantez ve OR korunur. Sıyırma
    sonrası boş kalırsa orijinali aynen kullan (güvenli fallback).
    """
    cleaned = _X_OPERATOR_RE.sub(" ", query)
    cleaned = " ".join(cleaned.split())
    return cleaned or query


def _fetch_rss(query):
    """Nitter search RSS'i çek; instance'ları sırayla dene.

    Döndürür: (items, err). items = ElementTree <item> düğümleri listesi.
    err None ise başarılı. Tüm instance'lar düşerse (None, "kaynak yok").
    """
    q = urllib.parse.quote(_clean_query(query))
    last_err = "kaynak yok"
    for inst in _instances():
        url = f"{inst}/search/rss?f=tweets&q={q}"
        for attempt in range(_MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (EkranHisse)"})
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    body = resp.read()
                # Bazı instance'lar XML öncesi boşluk/yeni-satır ekler → ET.fromstring
                # "declaration not at start" hatası verir; baştaki boşluğu kırp.
                body = body.lstrip()
                root = ET.fromstring(body)
                # RSS: rss/channel/item
                items = root.findall(".//item")
                return items, None
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < _MAX_RETRIES:
                    retry_after = e.headers.get("Retry-After")
                    try:
                        wait = min(_MAX_BACKOFF, int(retry_after)) if retry_after else 5
                    except ValueError:
                        wait = 5
                    log.info("Nitter 429 (%s); %ss bekleniyor (deneme %d)",
                             inst, wait, attempt + 1)
                    time.sleep(wait)
                    continue
                log.warning("Nitter HTTP hatası (%s): %s", inst, e.code)
                last_err = "rate-limit" if e.code == 429 else f"hata {e.code}"
                break   # bu instance'ta 429 dışı hata → sıradaki instance
            except ET.ParseError as e:
                log.warning("Nitter RSS parse hatası (%s): %s", inst, e)
                last_err = "geçersiz yanıt"
                break
            except Exception as e:
                log.warning("Nitter isteği başarısız (%s): %s", inst, e)
                last_err = "ağ hatası"
                break
    return None, last_err


def _text(item, tag):
    """<item> altındaki bir alt-etiketin metnini döndür (namespace toleranslı)."""
    el = item.find(tag)
    if el is not None and el.text:
        return el.text
    # dc:creator gibi namespace'li etiketler için sonek eşleşmesi
    local = tag.split(":")[-1]
    for child in item:
        if child.tag.split("}")[-1] == local and child.text:
            return child.text
    return ""


def _parse_item(item):
    """RSS <item> → (tweet_dict, username, name).

    tweet_dict: {"id","text","created_at","author_id"}. author_id = username
    (Nitter'da ayrı numeric id yok). created_at ISO8601 (tw_ago bunu parse eder).
    """
    link = _text(item, "link") or _text(item, "guid")
    m = _STATUS_ID_RE.search(link)
    tid = m.group(1) if m else link

    title = html.unescape(_text(item, "title"))
    text = " ".join(title.split())

    # created_at: RFC822 pubDate → ISO8601. Parse edilemezse boş bırak (tw_ago
    # boş girişi zaten '' yapar).
    created = ""
    pub = _text(item, "pubDate")
    if pub:
        try:
            created = parsedate_to_datetime(pub).isoformat()
        except (TypeError, ValueError):
            created = ""

    # username: dc:creator ('@handle') öncelikli; yoksa boş.
    creator = _text(item, "dc:creator") or _text(item, "creator")
    username = creator.lstrip("@").strip()
    name = username

    tweet = {
        "id": tid,
        "text": text,
        "created_at": created,
        "author_id": username,
    }
    return tweet, username, name


def fetch_recent(query, callback):
    """Son tweet'leri (metin+kullanıcı) çeker. callback((tweets, users, err))."""
    def _run():
        items, err = _fetch_rss(query)
        if err is not None:
            callback(([], {}, err))
            return
        tweets = []
        users = {}
        for it in items:
            tw, username, name = _parse_item(it)
            tweets.append(tw)
            if username:
                users[username] = {"username": username, "name": name}
        callback((tweets, users, None))
    threading.Thread(target=_run, daemon=True).start()


def fetch_ids(query, callback):
    """Sadece tweet id'lerini çeker (poll için ucuz). callback((ids_set, err))."""
    def _run():
        items, err = _fetch_rss(query)
        if err is not None:
            callback((set(), err))
            return
        ids = set()
        for it in items:
            tw, _u, _n = _parse_item(it)
            if tw["id"]:
                ids.add(tw["id"])
        callback((ids, None))
    threading.Thread(target=_run, daemon=True).start()
