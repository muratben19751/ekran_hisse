"""EkranHisse — merkezî yapılandırma (sır okuma tek yerden).

Sır arama sırası (her anahtar için ayrı ayrı):
  1. macOS Keychain  (güvenli — önerilen)
       security add-generic-password -s ekranhisse -a GITHUB_TOKEN -w '<token>'
  2. ~/.ekranhisse/notes_config.env  (kullanıcı dizini — düz metin)
  3. <proje dizini>/notes_config.env (eski konum — geriye dönük uyumluluk)

Sırlar env dosyasında düz metin bulunursa bir kez uyarı loglanır; token'lar
Keychain'e taşınmalıdır (bkz. NASIL-UYGULANIR.md).
"""

import os
import subprocess

from applog import log

_USER_CFG  = os.path.expanduser("~/.ekranhisse/notes_config.env")
_LOCAL_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_config.env")
_CFG_FILE  = _USER_CFG if os.path.exists(_USER_CFG) else _LOCAL_CFG

_KEYCHAIN_SERVICE = "ekranhisse"
# Bu anahtarlar sırdır; env'de düz metin görülürse uyarı verilir.
_SECRET_KEYS = {"GITHUB_TOKEN", "TWITTER_BEARER_TOKEN", "TV_SESSION_ID"}


def _load_env():
    cfg = {}
    if os.path.exists(_CFG_FILE):
        try:
            with open(_CFG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
        except OSError as e:
            log.warning("config env okunamadı (%s): %s", _CFG_FILE, e)
    return cfg


def _keychain_get(key):
    """macOS Keychain'den generic-password oku. Yoksa/hatada None."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE,
             "-a", key, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


_ENV = _load_env()
_warned_plaintext = False


def get(key, default=""):
    """Önce Keychain, sonra env dosyası. Sır env'de düz metinse bir kez uyar."""
    global _warned_plaintext
    val = _keychain_get(key)
    if val:
        return val
    val = _ENV.get(key)
    if val:
        if key in _SECRET_KEYS and not _warned_plaintext:
            _warned_plaintext = True
            log.warning(
                "Sırlar env dosyasında DÜZ METİN olarak duruyor (%s). "
                "Güvenlik için Keychain'e taşıyın: "
                "security add-generic-password -s %s -a <ANAHTAR> -w '<değer>'",
                _CFG_FILE, _KEYCHAIN_SERVICE,
            )
        return val
    return default


GIST_ID              = get("GIST_ID")
GITHUB_TOKEN         = get("GITHUB_TOKEN")
TWITTER_BEARER_TOKEN = get("TWITTER_BEARER_TOKEN")
TV_SESSION_ID        = get("TV_SESSION_ID")
# notes_config.env'de tanımlıydı ama okunmuyordu; artık opsiyonel override.
# Boşsa logic.twitter_query() sembollerden üretir.
TWITTER_QUERY        = get("TWITTER_QUERY")
