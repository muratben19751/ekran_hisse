"""EkranHisse — Twitter/X istemcisi (RSSHub user-timeline köprüsü, ağ katmanı).

X API v2 `search/recent` ücretli (kredi bitince HTTP 402), Nitter ekosistemi
çöktü, ve RSSHub `keyword` (search) route'u da X tarafında bozuldu (X arama
GraphQL endpoint'i `404` → RSSHub `503`). Bu modül aynı public arayüzü koruyarak
veriyi **self-hosted RSSHub** `/twitter/user/<handle>` route'undan (RSS XML)
çeker — user-timeline route'u çalışıyor (200). Sabit bir finans/borsa hesap
listesinin timeline'ları çekilir, gelen tweet'ler İZLENEN SEMBOLLERE göre
filtrelenir. RSSHub, X `auth_token` cookie'siyle (RSSHub tarafında
`TWITTER_AUTH_TOKEN`) gerçek timeline çeker; EkranHisse sır tutmaz. overlay/logic
ve callback sözleşmesi değişmez:

fetch_recent(query, callback)  → callback((tweets, users, err))
fetch_ids(query, callback)     → callback((ids_set, err))

tweets: [{"id","text","created_at","author_id"}]  (created_at ISO8601)
users:  {author_id: {"username","name"}}

RSSHub tabanı config.RSSHUB_URL ile verilir (boşsa http://localhost:1200).
İzlenen hesapların her biri için ayrı istek atılır; sonuçlar birleşir, id ile
tekilleşir, sorgudaki sembollerden en az birini içeren tweet'lere süzülür,
tarihe göre sıralanır. HTTP 429'da Retry-After'a saygı gösterilir.
"""

import html
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

import config
from applog import log

# RSSHub tabanı config'ten okunmazsa yerel Docker varsayılanı.
_DEFAULT_RSSHUB = "http://localhost:1200"

# İzlenecek X finans/borsa hesapları. config.TWITTER_ACCOUNTS (virgülle handle
# listesi) doluysa onu kullan; boşsa bu GÜNCEL + ticker-içeren Türk borsa hesabı
# seti. '@' ve boşluk temizlenir. keyword (arama) route'u X tarafında bozuk
# olduğu için tweet'ler bu hesapların timeline'larından gelir, sonra izlenen
# sembollere göre süzülür. Seçim kriteri: (1) hâlâ aktif tweet atıyor (RSSHub
# bazı hesapların yıllar önceki cache'ini verir — ör. borsainsan 2021'de kalmış,
# işe yaramaz), (2) tweet'lerinde ticker (#SEMBOL/$SEMBOL) geçiyor (makro-haber
# ağırlıklı hesaplar sembol filtresinden geçmez). Aracı kurum hesapları
# (bilanço/öneri) ve borsagundem düzenli ticker kullanır.
_DEFAULT_ACCOUNTS = [
    "isyatirim",
    "ziraatyatirim",
    "oyakyatirim",
    "fintables",
    "borsagundem",
]

_MAX_RETRIES = 2          # bir istekte 429 sonrası en fazla bu kadar tekrar
_MAX_BACKOFF = 30         # Retry-After'ı bu saniyeyle sınırla (UI'yı kilitleme)
_TIMEOUT = 15
_MAX_WORKERS = 6          # timeline istekleri için eşzamanlı thread üst sınırı

# X-özel arama operatörleri (sorgudan sembol çıkarırken yok say) — sıyır.
_X_OPERATOR_RE = re.compile(r"(?:^|\s)-?(?:lang|is|filter):\S+", re.IGNORECASE)
_STATUS_ID_RE = re.compile(r"/status/(\d+)")
# Tweet link'inden handle: twitter.com/<handle>/status/... veya x.com/<handle>/...
_HANDLE_RE = re.compile(r"(?:twitter|x)\.com/([^/]+)/status/", re.IGNORECASE)


def _rsshub_base():
    """config.RSSHUB_URL (boşsa yerel Docker varsayılanı), sondaki '/' kırpılı."""
    raw = (config.RSSHUB_URL or "").strip()
    return (raw or _DEFAULT_RSSHUB).rstrip("/")


def _accounts():
    """İzlenecek X handle listesi: config.TWITTER_ACCOUNTS varsa o, yoksa varsayılan."""
    raw = (getattr(config, "TWITTER_ACCOUNTS", "") or "").strip()
    if raw:
        out = [h.strip().lstrip("@") for h in raw.split(",")]
        return [h for h in out if h]
    return list(_DEFAULT_ACCOUNTS)


def _symbols_from_query(query):
    """X-stili sorgudan izlenen sembol listesini çıkar (tweet filtresi için).

    logic.twitter_query() '(THYAO OR AKBNK) lang:tr -is:retweet' üretir. Filtre
    için sadece sembol terimleri gerekir: operatörleri, parantezleri ve 'OR'
    ayracını sıyırıp geriye kalan terimleri (yinelemesiz) büyük harfle döndür.
    """
    cleaned = _X_OPERATOR_RE.sub(" ", query)
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    seen = set()
    out = []
    for t in cleaned.split():
        u = t.upper()
        if u and u != "OR" and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _matches_symbols(text, symbols):
    """text (büyük harf) izlenen sembollerden en az birini kelime sınırıyla içerir mi?

    symbols boşsa (sembol yok) True — filtre uygulanmaz. Kelime sınırı: sembolün
    öncesi/sonrası harf-rakam OLMAMALI ('THYAO' 'THYAOX' ile eşleşmesin).
    """
    if not symbols:
        return True
    for s in symbols:
        # (?<![A-Z0-9])SYM(?![A-Z0-9]) — logic._sym_regex ile aynı mantık
        m = re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", text)
        if m:
            return True
    return False


def _fetch_one(handle):
    """Tek hesap için RSSHub user-timeline'ına istek at; (items, err) döndür.

    items = ElementTree <item> düğümleri. err None ise başarılı. 429'da
    Retry-After'a (cap'li) saygı gösterip aynı istekte _MAX_RETRIES kez dener.
    """
    base = _rsshub_base()
    q = urllib.parse.quote(handle)
    # showRetweets=0: retweet'leri ele (eski '-is:retweet' niyetini korur).
    url = f"{base}/twitter/user/{q}?showRetweets=0"
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
                         handle, wait, attempt + 1)
                time.sleep(wait)
                continue
            log.warning("RSSHub HTTP hatası (%s): %s", handle, e.code)
            if e.code == 429:
                return None, "rate-limit"
            # 503: RSSHub ayakta ama X'ten veri gelmedi — token geçersiz/expire
            # (RSSHub içeride X'ten 404/401 alıp 503'e çeviriyor).
            if e.code == 503:
                return None, "X oturumu geçersiz (RSSHub token'ı yenile)"
            return None, f"hata {e.code}"
        except ET.ParseError as e:
            log.warning("RSSHub RSS parse hatası (%s): %s", handle, e)
            return None, "geçersiz yanıt"
        except (urllib.error.URLError, OSError) as e:
            # localhost kapalı / bağlantı reddi → RSSHub çalışmıyor olabilir.
            log.warning("RSSHub'a ulaşılamadı (%s): %s", handle, e)
            return None, "RSSHub kapalı"
        except Exception as e:
            log.warning("RSSHub isteği başarısız (%s): %s", handle, e)
            return None, "ağ hatası"
    # Buraya yalnızca son denemede 429+continue ile döngü tükenirse düşülür;
    # pratikte son iterasyonda 429 dalı return'e girer, yine de savunma amaçlı.
    return None, "rate-limit"


def _fetch_items(query):
    """İzlenen her hesap için RSSHub user-timeline'ını çek; birleşik (items, err).

    Her hesap ayrı thread'de PARALEL çekilir (sıralı değil): K hesapta toplam
    süre ~max(istek) seviyesinde kalır, K×gecikme'ye çıkmaz. En az bir hesap
    başarılıysa kısmi sonuç döner (err None). Tüm hesaplar düşerse
    (None, son_hata). Sembol filtresi/tekilleştirme/sıralama çağıran tarafından
    _parse_item sonrası yapılır. query yalnızca hesap listesi seçiminde değil,
    çağıran katmanda sembol filtresi için kullanılır (buradan geçirilmez).
    """
    handles = _accounts()
    if not handles:
        return None, "kaynak yok"
    all_items = []
    last_err = "kaynak yok"
    any_ok = False
    # Eşzamanlılığı hesap sayısıyla sınırla (tek hesapta thread havuzu kurma).
    workers = min(len(handles), _MAX_WORKERS)
    if workers <= 1:
        results = [_fetch_one(h) for h in handles]
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_fetch_one, handles))
    for items, err in results:
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
    (handle; ayrı numeric id yok). created_at ISO8601 (tw_ago bunu parse eder;
    zaman dilimsiz gelebilir). user-timeline route'unda dc:creator olmayabilir;
    handle o zaman tweet link'inden (twitter.com/<handle>/status/...) çıkarılır,
    görünen ad <author>'dan alınır.
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

    # username (handle): dc:creator ('@handle') öncelikli; yoksa link'ten çıkar.
    # user-timeline route dc:creator vermeyebiliyor → handle link'ten gelir.
    creator = _text(item, "dc:creator") or _text(item, "creator")
    username = creator.lstrip("@").strip()
    if not username:
        hm = _HANDLE_RE.search(link)
        if hm:
            username = hm.group(1)
    # görünen ad: <author> (display-name) varsa o, yoksa handle.
    name = _text(item, "author").strip() or username

    tweet = {
        "id": tid,
        "text": text,
        "created_at": created,
        "author_id": username,
    }
    return tweet, username, name


def fetch_recent(query, callback):
    """Son tweet'leri (metin+kullanıcı) çeker. callback((tweets, users, err)).

    İzlenen hesapların timeline'ları birleşir; sorgudaki sembollerden en az
    birini içeren tweet'lere süzülür (sorguda sembol yoksa süzme yapılmaz),
    id ile tekilleşir ve created_at'e göre azalan sıralanır (boş created_at'ler
    sona).
    """
    def _run():
        items, err = _fetch_items(query)
        if err is not None:
            callback(([], {}, err))
            return
        symbols = _symbols_from_query(query)
        tweets = []
        users = {}
        seen_ids = set()
        for it in items:
            tw, username, name = _parse_item(it)
            if not _matches_symbols(tw["text"].upper(), symbols):
                continue
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
    """Sadece tweet id'lerini çeker (poll için ucuz). callback((ids_set, err)).

    fetch_recent ile aynı sembol filtresi uygulanır; aksi halde poll'de gelen
    id'ler ile fetch_recent'in gösterdiği tweet'ler uyuşmaz ve okunmamış sayacı
    şişerdi.
    """
    def _run():
        items, err = _fetch_items(query)
        if err is not None:
            callback((set(), err))
            return
        symbols = _symbols_from_query(query)
        ids = set()
        for it in items:
            tw, _u, _n = _parse_item(it)
            if not _matches_symbols(tw["text"].upper(), symbols):
                continue
            if tw["id"]:
                ids.add(tw["id"])
        callback((ids, None))
    threading.Thread(target=_run, daemon=True).start()
