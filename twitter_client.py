"""EkranHisse — Twitter/X istemcisi (RSSHub keyword köprüsü, ağ katmanı).

X API v2 `search/recent` ücretli (kredi bitince HTTP 402) ve Nitter ekosistemi
çöktü (instance'lar 403/kapalı/anti-bot). Bu modül aynı public arayüzü koruyarak
veriyi **self-hosted RSSHub** `/twitter/keyword/<terim>` route'undan (RSS XML)
çeker. RSSHub, X `auth_token` cookie'siyle (RSSHub tarafında `TWITTER_AUTH_TOKEN`)
gerçek keyword search yapar; EkranHisse sır tutmaz. overlay/logic ve callback
sözleşmesi değişmez:

fetch_recent(query, callback)  → callback((tweets, users, err))
fetch_ids(query, callback)     → callback((ids_set, err))

tweets: [{"id","text","created_at","author_id"}]  (created_at ISO8601)
users:  {author_id: {"username","name"}}

RSSHub tabanı config.RSSHUB_URL ile verilir (boşsa http://localhost:1200).
İzlenen birden çok sembol için her sembole ayrı istek atılır; sonuçlar birleşir,
id ile tekilleşir, tarihe göre sıralanır. HTTP 429'da Retry-After'a saygı gösterilir.
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

# RSSHub tabanı config'ten okunmazsa yerel Docker varsayılanı.
_DEFAULT_RSSHUB = "http://localhost:1200"

_MAX_RETRIES = 2          # bir istekte 429 sonrası en fazla bu kadar tekrar
_MAX_BACKOFF = 30         # Retry-After'ı bu saniyeyle sınırla (UI'yı kilitleme)
_TIMEOUT = 10

# X-özel arama operatörleri (keyword route yok sayar) — sorgudan sıyır.
_X_OPERATOR_RE = re.compile(r"(?:^|\s)-?(?:lang|is|filter):\S+", re.IGNORECASE)
_STATUS_ID_RE = re.compile(r"/status/(\d+)")


def _rsshub_base():
    """config.RSSHUB_URL (boşsa yerel Docker varsayılanı), sondaki '/' kırpılı."""
    raw = (config.RSSHUB_URL or "").strip()
    return (raw or _DEFAULT_RSSHUB).rstrip("/")


def _keyword_from_query(query):
    """X-stili sorgudan RSSHub keyword terim listesi çıkar.

    logic.twitter_query() '(THYAO OR AKBNK) lang:tr -is:retweet' üretir; RSSHub
    keyword route bu operatörleri anlamaz. lang:/is:/filter: operatörlerini,
    parantezleri ve 'OR' ayracını sıyırıp geriye kalan terimleri döndür. Hiç
    terim kalmazsa (güvenli fallback) sorgunun tamamını tek terim say.
    """
    cleaned = _X_OPERATOR_RE.sub(" ", query)
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    terms = [t for t in cleaned.split() if t and t.upper() != "OR"]
    if terms:
        # yinelemesiz, sırayı koru
        seen = set()
        out = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out
    stripped = query.strip()
    return [stripped] if stripped else []


def _fetch_one(keyword):
    """Tek keyword için RSSHub'a istek at; (items, err) döndür.

    items = ElementTree <item> düğümleri. err None ise başarılı. 429'da
    Retry-After'a (cap'li) saygı gösterip aynı istekte _MAX_RETRIES kez dener.
    """
    base = _rsshub_base()
    q = urllib.parse.quote(keyword)
    url = f"{base}/twitter/keyword/{q}"
    last_err = "kaynak yok"
    for attempt in range(_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (EkranHisse)"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read()
            # Bazı yanıtlar XML öncesi boşluk ekler → ET.fromstring "declaration
            # not at start" hatası verir; baştaki boşluğu kırp.
            body = body.lstrip()
            root = ET.fromstring(body)
            items = root.findall(".//item")
            return items, None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _MAX_RETRIES:
                retry_after = e.headers.get("Retry-After")
                try:
                    wait = min(_MAX_BACKOFF, int(retry_after)) if retry_after else 5
                except ValueError:
                    wait = 5
                log.info("RSSHub 429 (%s); %ss bekleniyor (deneme %d)",
                         keyword, wait, attempt + 1)
                time.sleep(wait)
                continue
            log.warning("RSSHub HTTP hatası (%s): %s", keyword, e.code)
            return None, "rate-limit" if e.code == 429 else f"hata {e.code}"
        except ET.ParseError as e:
            log.warning("RSSHub RSS parse hatası (%s): %s", keyword, e)
            return None, "geçersiz yanıt"
        except (urllib.error.URLError, OSError) as e:
            # localhost kapalı / bağlantı reddi → RSSHub çalışmıyor olabilir.
            log.warning("RSSHub'a ulaşılamadı (%s): %s", keyword, e)
            return None, "RSSHub kapalı"
        except Exception as e:
            log.warning("RSSHub isteği başarısız (%s): %s", keyword, e)
            return None, "ağ hatası"
    return None, last_err


def _fetch_items(query):
    """Sorgudaki her sembol için RSSHub'ı çek; birleşik (items, err) döndür.

    En az bir sembol başarılıysa kısmi sonuç döner (err None). Tüm semboller
    düşerse (None, son_hata). Sıralama/tekilleştirme çağıran (fetch_recent/
    fetch_ids) tarafından _parse_item sonrası yapılır.
    """
    keywords = _keyword_from_query(query)
    if not keywords:
        return None, "kaynak yok"
    all_items = []
    last_err = "kaynak yok"
    any_ok = False
    for kw in keywords:
        items, err = _fetch_one(kw)
        if err is None:
            any_ok = True
            all_items.extend(items)
        else:
            last_err = err
    if any_ok:
        return all_items, None
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
    """Son tweet'leri (metin+kullanıcı) çeker. callback((tweets, users, err)).

    Çoklu sembolde birleşik akış id ile tekilleşir ve created_at'e göre azalan
    sıralanır (boş created_at'ler sona).
    """
    def _run():
        items, err = _fetch_items(query)
        if err is not None:
            callback(([], {}, err))
            return
        tweets = []
        users = {}
        seen_ids = set()
        for it in items:
            tw, username, name = _parse_item(it)
            tid = tw["id"]
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            tweets.append(tw)
            if username:
                users[username] = {"username": username, "name": name}
        tweets.sort(key=lambda t: t.get("created_at") or "", reverse=True)
        callback((tweets, users, None))
    threading.Thread(target=_run, daemon=True).start()


def fetch_ids(query, callback):
    """Sadece tweet id'lerini çeker (poll için ucuz). callback((ids_set, err))."""
    def _run():
        items, err = _fetch_items(query)
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
