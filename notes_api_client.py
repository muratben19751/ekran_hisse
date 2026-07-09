import threading
import urllib.request
import urllib.parse
import json

API_URL = "https://muratben.com/notes_api.php"
SECRET  = "ekranhisse_secret_2024"


def _request(data=None):
    try:
        headers = {"X-Secret": SECRET}
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                API_URL,
                data=payload,
                headers=headers,
                method="POST",
            )
        else:
            req = urllib.request.Request(API_URL, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("notes_api hatası:", e)
        return None


def fetch_notes(callback):
    def _run():
        result = _request()
        notes = result.get("notes", []) if result else []
        callback(notes)
    threading.Thread(target=_run, daemon=True).start()


def save_notes(notes, callback=None):
    def _run():
        result = _request({"action": "save", "notes": notes})
        if callback:
            callback(result)
    threading.Thread(target=_run, daemon=True).start()
