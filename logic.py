"""EkranHisse — saf iş mantığı (Qt bağımsız, birim test edilebilir).

Bu modüldeki hiçbir fonksiyon Qt/PySide6'ya, ağ'a veya diske dokunmaz.
overlay.py bunları çağırır; testler doğrudan import edip test edebilir.
"""

import math
import re
from datetime import datetime, timezone

_SEP_SYMBOL = "---"
# Bölüm uid alan ayracı: bölüm adında ':' geçse bile çakışmaması için görünmez
# birim-ayracı (US, \x1f) kullanılır. Eski ':' formatı geriye dönük okunur.
_SEP_FIELD = "\x1f"


def make_sep_symbol(name: str, counter) -> str:
    """Bölüm adı + sayaçtan uid üret: '---\\x1f<ad>\\x1f<sayaç>'."""
    return f"{_SEP_SYMBOL}{_SEP_FIELD}{name}{_SEP_FIELD}{counter}"


def tr_number(v, d=2):
    """1234.5 → '1.234,50' (TR biçimi: nokta binlik, virgül ondalık)."""
    s = f"{v:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def tw_ago(iso, now=None):
    """'2026-07-31T11:02:00.000Z' → 'şimdi' / '12dk' / '3sa' / '2g'.

    now verilmezse UTC şimdi kullanılır (test için enjekte edilebilir).
    """
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[11:16]
    ref = now or datetime.now(timezone.utc)
    secs = (ref - t).total_seconds()
    if secs < 60:
        return "şimdi"
    if secs < 3600:
        return f"{int(secs // 60)}dk"
    if secs < 86400:
        return f"{int(secs // 3600)}sa"
    return f"{int(secs // 86400)}g"


def parse_price(val: str) -> float:
    """'1.234,50' / '62,30' / '62.30' / '1,234.50' / '1 234,50' → float.

    Hem ',' hem '.' varsa: SONDAKİ ayraç ondalık kabul edilir, diğeri binlik
    ayracı sayılıp silinir (TR '1.234,50' ve US '1,234.50' ikisi de doğru).
    Boşluk / kırılmaz boşluk (U+00A0) / dar boşluk (U+202F) binlik ayracı
    olarak silinir ('1 234,50' → 1234.50). Python-tarzı alt tire ('1_000')
    reddedilir. inf/nan gibi sonlu olmayan değerler reddedilir.
    """
    v = val.strip()
    if "_" in v:                          # float('1_000')==1000 sürprizini engelle
        raise ValueError(f"geçersiz sayı: {val!r}")
    # Boşluk türlerini (normal, kırılmaz, dar) binlik ayracı say ve sil.
    for ws in (" ", " ", " ", "\t"):
        v = v.replace(ws, "")
    if ',' in v and '.' in v:
        if v.rfind(',') > v.rfind('.'):   # virgül sonda → TR biçimi
            v = v.replace('.', '').replace(',', '.')
        else:                             # nokta sonda → US biçimi
            v = v.replace(',', '')
    else:
        v = v.replace(',', '.')
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"sonlu olmayan sayı: {val!r}")
    return f


def parse_sep_symbol(symbol: str):
    """Bölüm uid → (ad, sayaç). Yeni '\\x1f' ve eski ':' formatını okur.

    '---\\x1fAd\\x1f3' → ('Ad', '3'); '---:Ad:3' → ('Ad', '3');
    '---:Ad' → ('', 'Ad'); diğer → ('', '0'). Ad içinde ':' geçse bile
    yeni formatta doğru ayrışır (ayraç görünmez birim-ayracıdır).
    """
    sep = _SEP_FIELD if _SEP_FIELD in symbol else ":"
    parts = symbol.split(sep, 2)
    if len(parts) == 3:
        return parts[1], parts[2]
    if len(parts) == 2:
        return "", parts[1]
    return "", "0"


def twitter_query(symbols) -> str:
    """İzlenen sembollerden Twitter arama sorgusu üret."""
    syms = [s for s in symbols if s]
    if not syms:
        return "TTKOM lang:tr -is:retweet"
    if len(syms) == 1:
        return f"{syms[0]} lang:tr -is:retweet"
    return "(" + " OR ".join(syms) + ") lang:tr -is:retweet"


_SYM_RE_CACHE = {}


def _sym_regex(s: str):
    r = _SYM_RE_CACHE.get(s)
    if r is None:
        # kelime sınırı: harf/rakam olmayan ya da $ ile çevrili
        r = re.compile(rf"(?<![A-Z0-9]){re.escape(s.upper())}(?![A-Z0-9])")
        _SYM_RE_CACHE[s] = r
    return r


def symbols_of_tweet(text: str, symbols) -> list:
    """Tweet metninde geçen TÜM izlenen sembolleri döndür (kelime sınırıyla).

    Bir tweet birden çok sembolden bahsedebilir ('THYAO ve AKBNK yükseldi');
    tek sembole bağlamak chip sayaçlarını yanıltır ve tweet bir sembolün
    filtresinde görünmez olur. Bu yüzden eşleşen sembollerin tümünü, verilen
    'symbols' sırasında (yinelemesiz) döndürürüz.
    """
    up = text.upper()
    out = []
    for s in symbols:
        if not s or s in out:
            continue
        if _sym_regex(s).search(up):
            out.append(s)
    return out


def symbol_of_tweet(text: str, symbols) -> str:
    """Tweet metninde geçen ilk izlenen sembolü döndür (geriye dönük uyumluluk).

    Yeni kod çok-sembollü doğru davranış için symbols_of_tweet kullanmalıdır.
    """
    matches = symbols_of_tweet(text, symbols)
    return matches[0] if matches else ""


def compute_unread(incoming_ids: set, seen_ids: set, active: bool):
    """Gelen tweet id'lerinden yeni/okunmamış hesapla.

    İlk yüklemede (seen boş) hiçbir şey 'yeni' sayılmaz — sadece tohumlanır.
    Döndürür: (new_ids, next_seen). active=True ise sekme açık, unread sayılmaz.
    """
    next_seen = seen_ids | incoming_ids
    if not seen_ids:
        return set(), next_seen          # ilk yükleme: sadece tohumla
    if active:
        return set(), next_seen          # sekme açık: okunmamış yok
    new_ids = incoming_ids - seen_ids
    return new_ids, next_seen


def sanitize_notes(notes):
    """Dış kaynaktan (Gist) gelen not listesini güvenli hale getir.

    Yalnızca dict öğeleri tutulur; 'title'/'body' string'e zorlanır ve eksikse
    boş string yapılır. dict olmayan öğeler (string/None/sayı) atılır — böylece
    UI'daki n.get('title') çağrıları AttributeError ile çökmez.
    """
    if not isinstance(notes, list):
        return []
    out = []
    for n in notes:
        if not isinstance(n, dict):
            continue
        title = n.get("title", "")
        body = n.get("body", "")
        out.append({
            "title": title if isinstance(title, str) else str(title),
            "body": body if isinstance(body, str) else str(body),
        })
    return out


def sanitize_stocks(stocks):
    """Dış kaynaktan (elle düzenlenen stocks.json) gelen listeyi güvenli hale getir.

    Yalnızca dict öğeleri ve 'symbol' değeri boş-olmayan string olan kayıtlar
    tutulur. symbol str'e zorlanır (int/None gibi değerler group_stocks/reorder
    içindeki .startswith/== çağrılarını AttributeError ile çökertmesin). entry/exit
    yalnızca sayı ise korunur, aksi halde None yapılır.
    """
    if not isinstance(stocks, list):
        return []
    out = []
    for s in stocks:
        if not isinstance(s, dict):
            continue
        sym = s.get("symbol")
        if not isinstance(sym, str) or not sym.strip():
            continue
        rec = {"symbol": sym}
        for k in ("entry", "exit", "qty", "mult"):
            if k in s:
                v = s[k]
                rec[k] = v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        out.append(rec)
    return out


def compute_pnl(entry, price, qty=None, mult=None):
    """Giriş fiyatı + güncel fiyat (+ opsiyonel adet, çarpan) → (tutar, yüzde).

    Döndürür `(amount, pct)`:
      - `entry`/`price` None ya da `entry == 0` ise `(None, None)` — hesap yok.
      - `pct` = `(price - entry) / entry * 100` (giriş+fiyat varsa her zaman).
      - `amount` = `(price - entry) * qty * mult` yalnızca `qty` geçerli bir sayı ve
        `> 0` ise; aksi halde `None` (adet opsiyonel — girilmezse yalnız yüzde).
        `mult` VİOP gibi kontrat çarpanıdır (ör. 100); geçersiz/None/≤0 ise 1 sayılır.
        Yüzdeyi ETKİLEMEZ — sadece tutarı ölçekler.
    Long/short ayrımı yok: negatif tutar/yüzde zararı gösterir.
    """
    if entry is None or price is None or entry == 0:
        return None, None
    pct = (price - entry) / entry * 100
    amount = None
    if isinstance(qty, (int, float)) and not isinstance(qty, bool) and qty > 0:
        m = mult if isinstance(mult, (int, float)) and not isinstance(mult, bool) and mult > 0 else 1
        amount = (price - entry) * qty * m
    return amount, pct


def group_stocks(stocks, sep=_SEP_SYMBOL):
    """Stok listesini [(sep_uid or None, [stock dict, ...]), ...] gruplarına ayır."""
    groups = []
    current = (None, [])
    for s in stocks:
        sym = s["symbol"]
        if sym.startswith(sep):
            groups.append(current)
            current = (sym, [])
        else:
            current[1].append(s)
    groups.append(current)
    return groups


def next_separator_counter(stocks, sep=_SEP_SYMBOL):
    """Yeni bölüm için benzersiz sayaç değeri üret."""
    counters = []
    for s in stocks:
        if s["symbol"].startswith(sep):
            _, c = parse_sep_symbol(s["symbol"])
            if c.isdigit():
                counters.append(int(c))
    return (max(counters) + 1) if counters else 0


def reorder(stocks, moved, target, after=False):
    """`moved` sembolünü taşı: after=False → `target`'ın ÖNÜNE, after=True → ARDINA.

    target None → listenin SONUNA. after=True özellikle bir bölüm başlığına
    bırakınca kullanılır: hisse başlığın hemen ardına, yani o bölümün İLK
    öğesi olarak yerleşir. Yeni liste döndürür; girdi listesi değişmez.
    """
    idx = next((i for i, s in enumerate(stocks) if s["symbol"] == moved), None)
    if idx is None:
        return list(stocks)
    out = list(stocks)
    item = out.pop(idx)
    if target is None or target == moved:
        out.append(item)
    else:
        tgt = next((i for i, s in enumerate(out) if s["symbol"] == target), None)
        if tgt is None:                       # hedef bulunamadı → sona (eski davranış)
            out.append(item)
        else:
            out.insert(tgt + 1 if after else tgt, item)
    return out
