"""EkranHisse — Twitter/X API istemcisi (ağ katmanı).

Twitter erişimini UI'dan (overlay) ayırır; notes_api_client deseniyle aynı
callback yaklaşımı. HTTP 429 (rate-limit) için Retry-After header'ına saygı
gösterir ve sınırlı yeniden deneme yapar.

fetch_recent(query, callback)  → callback((tweets, users, err))
fetch_ids(query, callback)     → callback((ids_set, err))
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import config
from applog import log

_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
_MAX_RETRIES = 2          # 429 sonrası en fazla bu kadar tekrar
_MAX_BACKOFF = 30         # Retry-After'ı bu saniyeyle sınırla (UI'yı kilitleme)


def _token():
    return config.TWITTER_BEARER_TOKEN


def _request(url):
    """URL'yi çeker; 429'da Retry-After kadar (sınırlı) bekleyip tekrar dener.

    Döndürür: (data_dict, err_str). err_str None ise başarılı.
    """
    token = _token()
    if not token:
        return None, "token yok"
    for attempt in range(_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode()), None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _MAX_RETRIES:
                retry_after = e.headers.get("Retry-After")
                try:
                    wait = min(_MAX_BACKOFF, int(retry_after)) if retry_after else 5
                except ValueError:
                    wait = 5
                log.info("Twitter 429 rate-limit; %ss bekleniyor (deneme %d)", wait, attempt + 1)
                time.sleep(wait)
                continue
            log.warning("Twitter HTTP hatası: %s", e.code)
            return None, ("rate-limit" if e.code == 429 else f"hata {e.code}")
        except Exception as e:
            log.warning("Twitter isteği başarısız: %s", e)
            return None, "ağ hatası"
    return None, "rate-limit"


def fetch_recent(query, callback):
    """Son tweet'leri (metin+kullanıcı) çeker. callback((tweets, users, err))."""
    def _run():
        url = (
            f"{_SEARCH_URL}?query={urllib.parse.quote(query)}&max_results=20"
            "&tweet.fields=created_at,author_id,text"
            "&expansions=author_id&user.fields=username,name"
        )
        data, err = _request(url)
        if err is not None:
            callback(([], {}, err))
            return
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        callback((tweets, users, None))
    threading.Thread(target=_run, daemon=True).start()


def fetch_ids(query, callback):
    """Sadece tweet id'lerini çeker (poll için ucuz). callback((ids_set, err))."""
    def _run():
        url = f"{_SEARCH_URL}?query={urllib.parse.quote(query)}&max_results=20&tweet.fields=id"
        data, err = _request(url)
        if err is not None:
            callback((set(), err))
            return
        ids = {tw.get("id", "") for tw in data.get("data", [])}
        callback((ids, None))
    threading.Thread(target=_run, daemon=True).start()
