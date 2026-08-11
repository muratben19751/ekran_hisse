import threading
import urllib.request
import json

import config
from applog import log

GIST_ID      = config.GIST_ID
GITHUB_TOKEN = config.GITHUB_TOKEN


class NotConfigured(Exception):
    """GIST_ID/GITHUB_TOKEN eksik — kurulum tamamlanmamış."""


def is_configured() -> bool:
    return bool(GIST_ID and GITHUB_TOKEN)


def _gist_api():
    if not GIST_ID:
        raise NotConfigured("GIST_ID yapılandırılmamış — notes_config.env / Keychain kontrol edin")
    return f"https://api.github.com/gists/{GIST_ID}"

_save_lock   = threading.Lock()
_pending     = None   # (notes, callback) | None
_save_thread = None


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def fetch_notes(callback):
    def _run():
        try:
            req = urllib.request.Request(_gist_api(), headers=_headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["files"]["notes.json"]["content"]
            notes = json.loads(content).get("notes", [])
            callback(notes)
        except NotConfigured as e:
            log.info("notes fetch atlandı: %s", e)
            callback("unconfigured")
        except Exception as e:
            log.warning("notes fetch hatası: %s", e)
            callback(None)
    threading.Thread(target=_run, daemon=True).start()


def save_notes(notes, callback=None):
    """En son payload'ı gönderir; uçuşta istek varsa beklemez, yenisiyle ezer."""
    global _pending, _save_thread
    with _save_lock:
        _pending = (notes, callback)
        if _save_thread is not None and _save_thread.is_alive():
            return
        _save_thread = threading.Thread(target=_save_worker, daemon=True)
        _save_thread.start()


def _save_worker():
    global _pending
    while True:
        with _save_lock:
            if _pending is None:
                return
            notes, callback = _pending
            _pending = None
        try:
            payload = json.dumps({
                "files": {
                    "notes.json": {
                        "content": json.dumps({"notes": notes}, ensure_ascii=False)
                    }
                }
            }).encode("utf-8")
            req = urllib.request.Request(_gist_api(), data=payload, headers=_headers(), method="PATCH")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            if callback:
                callback(True)
        except Exception as e:
            log.warning("notes save hatası: %s", e)
            if callback:
                callback(None)
