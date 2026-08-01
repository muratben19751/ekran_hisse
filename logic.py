"""EkranHisse — saf iş mantığı (Qt bağımsız, birim test edilebilir).

Bu modüldeki hiçbir fonksiyon Qt/PySide6'ya, ağ'a veya diske dokunmaz.
overlay.py bunları çağırır; testler doğrudan import edip test edebilir.
"""

import re

_SEP_SYMBOL = "---"


def tr_number(v, d=2):
    """1234.5 → '1.234,50' (TR biçimi: nokta binlik, virgül ondalık)."""
    s = f"{v:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def parse_price(val: str) -> float:
    """'1.234,50' / '62,30' / '62.30' / '1,234.50' → float. Bozuk girdide ValueError.

    Hem ',' hem '.' varsa: SONDAKİ ayraç ondalık kabul edilir, diğeri binlik
    ayracı sayılıp silinir (TR '1.234,50' ve US '1,234.50' ikisi de doğru).
    """
    v = val.strip()
    if ',' in v and '.' in v:
        if v.rfind(',') > v.rfind('.'):   # virgül sonda → TR biçimi
            v = v.replace('.', '').replace(',', '.')
        else:                             # nokta sonda → US biçimi
            v = v.replace(',', '')
    else:
        v = v.replace(',', '.')
    return float(v)


def parse_sep_symbol(symbol: str):
    """'---:Ad:3' → ('Ad', '3'); '---:Ad' → ('', 'Ad'); diğer → ('', '0')."""
    parts = symbol.split(":", 2)
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


def symbol_of_tweet(text: str, symbols) -> str:
    """Tweet metninde geçen ilk izlenen sembolü döndür (kelime sınırıyla).

    Substring yerine kelime sınırı kullanılır: 'AL' sembolü 'ALARM' içinde
    eşleşmez, ama '$AL', 'AL ', '#AL' eşleşir.
    """
    up = text.upper()
    for s in symbols:
        if not s:
            continue
        # kelime sınırı: harf/rakam olmayan ya da $ ile çevrili
        if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", up):
            return s
    return ""


def compute_unread(incoming_ids: set, seen_ids: set, active: bool):
    """Gelen tweet id'lerinden yeni/okunmamış hesapla.

    İlk yüklemede (seen boş) hiçbir şey 'yeni' sayılmaz — sadece tohumlanır.
    Döndürür: (new_ids, next_seen). active=True ise sekme açık, unread sayılmaz.
    """
    next_seen = seen_ids | incoming_ids
    if not seen_ids:
        return set(), next_seen          # ilk yükleme: sadece tohumla
    new_ids = incoming_ids - seen_ids
    return new_ids, next_seen


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
