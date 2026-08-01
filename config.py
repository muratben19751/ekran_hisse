"""EkranHisse — merkezî yapılandırma (env okuma tek yerden).

notes_config.env dosyasını bir kez okur; hem notes_api_client hem overlay
buradan okur. Böylece env parse mantığı tek yerde toplanır.
"""

import os

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_config.env")


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
