"""EkranHisse — merkezî yapılandırma (env okuma tek yerden).

notes_config.env dosyasını bir kez okur; hem notes_api_client hem overlay
buradan okur. Böylece env parse mantığı tek yerde toplanır.

Arama sırası:
  1. ~/.ekranhisse/notes_config.env  (kullanıcı dizini — önerilen)
  2. <proje dizini>/notes_config.env (eski konum — geriye dönük uyumluluk)
"""

import os

_USER_CFG  = os.path.expanduser("~/.ekranhisse/notes_config.env")
_LOCAL_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_config.env")
_CFG_FILE  = _USER_CFG if os.path.exists(_USER_CFG) else _LOCAL_CFG


def _load():
    cfg = {}
    if os.path.exists(_CFG_FILE):
        try:
            with open(_CFG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
        except OSError:
            pass
    return cfg


_CFG = _load()


def get(key, default=""):
    return _CFG.get(key, default)


GIST_ID              = get("GIST_ID")
GITHUB_TOKEN         = get("GITHUB_TOKEN")
TWITTER_BEARER_TOKEN = get("TWITTER_BEARER_TOKEN")
TV_SESSION_ID        = get("TV_SESSION_ID")
