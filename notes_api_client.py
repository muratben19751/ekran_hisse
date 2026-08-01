import threading
import urllib.request
import json

import config

GIST_ID      = config.GIST_ID
GITHUB_TOKEN = config.GITHUB_TOKEN
GIST_API     = f"https://api.github.com/gists/{GIST_ID}"


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def fetch_notes(callback):
    def _run():
        try:
            req = urllib.request.Request(GIST_API, headers=_headers(), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["files"]["notes.json"]["content"]
            notes = json.loads(content).get("notes", [])
            callback(notes)
        except Exception as e:
            print("notes fetch hatası:", e)
            callback(None)
    threading.Thread(target=_run, daemon=True).start()


def save_notes(notes, callback=None):
    def _run():
        try:
            payload = json.dumps({
                "files": {
                    "notes.json": {
                        "content": json.dumps({"notes": notes}, ensure_ascii=False)
                    }
                }
            }).encode("utf-8")
            req = urllib.request.Request(GIST_API, data=payload, headers=_headers(), method="PATCH")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            if callback:
                callback(True)
        except Exception as e:
            print("notes save hatası:", e)
            if callback:
                callback(None)
    threading.Thread(target=_run, daemon=True).start()
