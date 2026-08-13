"""logic.py — saf iş mantığı birim testleri."""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic

# ── tw_ago ────────────────────────────────────────────────────────────────────
_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("iso,expected", [
    ("2026-08-11T11:59:30.000Z", "şimdi"),   # 30 sn
    ("2026-08-11T11:48:00.000Z", "12dk"),    # 12 dk
    ("2026-08-11T09:00:00.000Z", "3sa"),     # 3 saat
    ("2026-08-09T12:00:00.000Z", "2g"),      # 2 gün
])
def test_tw_ago(iso, expected):
    assert logic.tw_ago(iso, now=_NOW) == expected


def test_tw_ago_empty():
    assert logic.tw_ago("") == ""


def test_tw_ago_malformed_falls_back_to_time_slice():
    # Parse edilemeyen iso → iso[11:16] dilimi döner
    bad = "XXXXXXXXXXX15:30stuff"
    assert logic.tw_ago(bad, now=_NOW) == bad[11:16]


# ── tr_number ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("value,expected", [
    (1234.5, "1.234,50"),
    (0, "0,00"),
    (-1234.5, "-1.234,50"),
    (1_000_000, "1.000.000,00"),
    (62.3, "62,30"),
])
def test_tr_number(value, expected):
    assert logic.tr_number(value) == expected


def test_tr_number_precision():
    assert logic.tr_number(1234.5, 1) == "1.234,5"
    assert logic.tr_number(1234.567, 0) == "1.235"


# ── parse_price ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("1.234,50", 1234.5),   # TR: nokta binlik, virgül ondalık
    ("62,30", 62.3),        # sadece virgül
    ("62.30", 62.3),        # sadece nokta
    ("1,234.50", 1234.5),   # US biçim
    ("-5,5", -5.5),
    ("  62,30  ", 62.3),    # boşluk kırpılır
])
def test_parse_price_valid(text, expected):
    assert logic.parse_price(text) == pytest.approx(expected)


@pytest.mark.parametrize("bad", ["", "abc", "1.2.3", "--"])
def test_parse_price_invalid(bad):
    with pytest.raises(ValueError):
        logic.parse_price(bad)


@pytest.mark.parametrize("bad", ["inf", "-inf", "nan", "Infinity"])
def test_parse_price_rejects_non_finite(bad):
    # inf/nan float() ile parse edilir ama finansal değer değildir → ValueError
    with pytest.raises(ValueError):
        logic.parse_price(bad)


# ── parse_sep_symbol ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("sym,expected", [
    ("---:Bankalar:3", ("Bankalar", "3")),
    ("---:Ad:0", ("Ad", "0")),
    ("---:AdVirgulsuz", ("", "AdVirgulsuz")),
    ("THYAO", ("", "0")),
    ("---:A:B:C", ("A", "B:C")),   # maxsplit=2
])
def test_parse_sep_symbol(sym, expected):
    assert logic.parse_sep_symbol(sym) == expected


# ── make_sep_symbol / parse round-trip (yeni \x1f formatı) ────────────────────
def test_make_sep_symbol_roundtrip():
    uid = logic.make_sep_symbol("Bankalar", 3)
    assert logic.parse_sep_symbol(uid) == ("Bankalar", "3")


def test_sep_symbol_name_with_colon():
    # Bölüm adında ':' geçse bile yeni format doğru ayrışır (eski ':' formatı bozardı)
    uid = logic.make_sep_symbol("Saat 15:30", 7)
    name, counter = logic.parse_sep_symbol(uid)
    assert name == "Saat 15:30"
    assert counter == "7"


def test_sep_symbol_starts_with_sep():
    # group_stocks ayracı _SEP_SYMBOL ile başlamaya güvenir
    uid = logic.make_sep_symbol("X", 0)
    assert uid.startswith(logic._SEP_SYMBOL)


# ── twitter_query ────────────────────────────────────────────────────────────
def test_twitter_query_empty():
    assert logic.twitter_query([]) == "TTKOM lang:tr -is:retweet"


def test_twitter_query_single():
    assert logic.twitter_query(["AKBNK"]) == "AKBNK lang:tr -is:retweet"


def test_twitter_query_multi():
    assert logic.twitter_query(["TTKOM", "AKBNK"]) == "(TTKOM OR AKBNK) lang:tr -is:retweet"


def test_twitter_query_filters_empty_strings():
    assert logic.twitter_query(["", "TTKOM", ""]) == "TTKOM lang:tr -is:retweet"


# ── symbol_of_tweet ──────────────────────────────────────────────────────────
def test_symbol_of_tweet_regex_cached():
    # İlk çağrı regex'i derleyip önbelleğe koyar; ikinci çağrı aynı sonucu verir.
    logic._SYM_RE_CACHE.clear()
    assert logic.symbol_of_tweet("THYAO ucdu", ["THYAO"]) == "THYAO"
    assert "THYAO" in logic._SYM_RE_CACHE   # önbelleğe alındı
    assert logic.symbol_of_tweet("yine THYAO", ["THYAO"]) == "THYAO"


def test_symbol_of_tweet_word_boundary():
    # "AL" 'ALARM' içinde eşleşMEmeli
    assert logic.symbol_of_tweet("ALARM verildi bugun", ["AL"]) == ""


def test_symbol_of_tweet_cashtag():
    assert logic.symbol_of_tweet("$AL yukseldi", ["AL"]) == "AL"


def test_symbol_of_tweet_plain():
    assert logic.symbol_of_tweet("TTKOM hedef 50", ["TTKOM"]) == "TTKOM"


def test_symbol_of_tweet_first_match():
    # birden fazla eşleşme → liste sırasına göre ilki
    assert logic.symbol_of_tweet("TTKOM ve AKBNK", ["AKBNK", "TTKOM"]) == "AKBNK"


def test_symbol_of_tweet_none():
    assert logic.symbol_of_tweet("borsa dustu", ["THYAO"]) == ""


# ── compute_unread ───────────────────────────────────────────────────────────
def test_compute_unread_first_load_seeds_only():
    new, seen = logic.compute_unread({"1", "2"}, set(), active=False)
    assert new == set()
    assert seen == {"1", "2"}


def test_compute_unread_new_ids():
    new, seen = logic.compute_unread({"1", "2", "3"}, {"1", "2"}, active=False)
    assert new == {"3"}
    assert seen == {"1", "2", "3"}


def test_compute_unread_no_new():
    new, seen = logic.compute_unread({"1", "2"}, {"1", "2"}, active=False)
    assert new == set()
    assert seen == {"1", "2"}


# ── group_stocks ─────────────────────────────────────────────────────────────
def test_group_stocks_no_separator():
    stocks = [{"symbol": "THYAO"}, {"symbol": "AKBNK"}]
    groups = logic.group_stocks(stocks)
    assert groups == [(None, [{"symbol": "THYAO"}, {"symbol": "AKBNK"}])]


def test_group_stocks_with_separator():
    stocks = [
        {"symbol": "THYAO"},
        {"symbol": "---:Bankalar:0"},
        {"symbol": "AKBNK"},
    ]
    groups = logic.group_stocks(stocks)
    assert groups[0] == (None, [{"symbol": "THYAO"}])
    assert groups[1] == ("---:Bankalar:0", [{"symbol": "AKBNK"}])


# ── next_separator_counter ───────────────────────────────────────────────────
def test_next_separator_counter_empty():
    assert logic.next_separator_counter([{"symbol": "THYAO"}]) == 0


def test_next_separator_counter_increments():
    stocks = [{"symbol": "---:A:0"}, {"symbol": "---:B:3"}]
    assert logic.next_separator_counter(stocks) == 4


# ── reorder ──────────────────────────────────────────────────────────────────
def test_reorder_to_end():
    stocks = [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}]
    out = logic.reorder(stocks, "A", None)
    assert [s["symbol"] for s in out] == ["B", "C", "A"]


def test_reorder_before_target():
    stocks = [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}]
    out = logic.reorder(stocks, "C", "A")
    assert [s["symbol"] for s in out] == ["C", "A", "B"]


def test_reorder_unknown_moved():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    out = logic.reorder(stocks, "X", "A")
    assert [s["symbol"] for s in out] == ["A", "B"]   # değişmez


def test_reorder_does_not_mutate_input():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    logic.reorder(stocks, "A", None)
    assert [s["symbol"] for s in stocks] == ["A", "B"]   # orijinal korunur


# ── reorder: after=True (bölüme sürükleme) ───────────────────────────────────
def test_reorder_after_target():
    stocks = [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}]
    out = logic.reorder(stocks, "C", "A", after=True)
    assert [s["symbol"] for s in out] == ["A", "C", "B"]


def test_reorder_into_section_first_item():
    # Hata senaryosu: THYAO'yu Bankalar başlığına bırak → bölümün İLK öğesi olur
    stocks = [
        {"symbol": "THYAO"},
        {"symbol": "---:Bankalar:0"},
        {"symbol": "AKBNK"},
    ]
    out = logic.reorder(stocks, "THYAO", "---:Bankalar:0", after=True)
    assert [s["symbol"] for s in out] == ["---:Bankalar:0", "THYAO", "AKBNK"]


def test_reorder_into_empty_section():
    stocks = [
        {"symbol": "AKBNK"},
        {"symbol": "---:Bos:1"},
    ]
    out = logic.reorder(stocks, "AKBNK", "---:Bos:1", after=True)
    assert [s["symbol"] for s in out] == ["---:Bos:1", "AKBNK"]


def test_reorder_after_own_header_is_noop_when_first():
    stocks = [
        {"symbol": "---:Bankalar:0"},
        {"symbol": "AKBNK"},
        {"symbol": "THYAO"},
    ]
    out = logic.reorder(stocks, "AKBNK", "---:Bankalar:0", after=True)
    assert [s["symbol"] for s in out] == ["---:Bankalar:0", "AKBNK", "THYAO"]


def test_reorder_after_moves_within_same_section():
    stocks = [
        {"symbol": "---:Bankalar:0"},
        {"symbol": "AKBNK"},
        {"symbol": "GARAN"},
        {"symbol": "THYAO"},
    ]
    out = logic.reorder(stocks, "THYAO", "---:Bankalar:0", after=True)
    assert [s["symbol"] for s in out] == ["---:Bankalar:0", "THYAO", "AKBNK", "GARAN"]


def test_reorder_after_target_none_appends():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    out = logic.reorder(stocks, "A", None, after=True)
    assert [s["symbol"] for s in out] == ["B", "A"]


def test_reorder_after_unknown_target_appends():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    out = logic.reorder(stocks, "A", "ZZZ", after=True)
    assert [s["symbol"] for s in out] == ["B", "A"]


def test_reorder_after_does_not_mutate_input():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    logic.reorder(stocks, "B", "A", after=True)
    assert [s["symbol"] for s in stocks] == ["A", "B"]


# ── parse_price: boşluk/kırılmaz-boşluk binlik ayracı + alt-tire reddi ────────
@pytest.mark.parametrize("text,expected", [
    ("1 234,50", 1234.50),      # normal boşluk binlik ayracı (TR)
    ("1 234,50", 1234.50), # kırılmaz boşluk (U+00A0)
    ("1 234.50", 1234.50), # dar boşluk (U+202F), US ondalık
    ("1 234 567", 1234567.0),   # birden çok boşluk
])
def test_parse_price_whitespace_thousands(text, expected):
    assert logic.parse_price(text) == pytest.approx(expected)


@pytest.mark.parametrize("bad", ["1_000", "1_000.5", "1__2"])
def test_parse_price_rejects_underscore(bad):
    # Python float('1_000')==1000 sürprizini engelle
    with pytest.raises(ValueError):
        logic.parse_price(bad)


# ── compute_unread: active=True dalı (sekme açık → okunmamış yok) ─────────────
def test_compute_unread_active_suppresses_unread():
    seen = {"a", "b"}
    incoming = {"a", "b", "c", "d"}   # c, d yeni ama sekme açık
    new_ids, next_seen = logic.compute_unread(incoming, seen, active=True)
    assert new_ids == set()                     # sekme açık: hiç unread
    assert next_seen == {"a", "b", "c", "d"}    # yine de tohumlanır


def test_compute_unread_active_still_seeds_on_first_load():
    new_ids, next_seen = logic.compute_unread({"x", "y"}, set(), active=True)
    assert new_ids == set()
    assert next_seen == {"x", "y"}


# ── reorder: moved==target, after=True (kendine bırakma) ──────────────────────
def test_reorder_move_onto_self_after_true():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    # 'A'yı 'A' üzerine after=True ile bırak → target==moved dalı: sona ekle
    out = logic.reorder(stocks, "A", "A", after=True)
    assert [s["symbol"] for s in out] == ["B", "A"]


def test_reorder_move_onto_self_after_false():
    stocks = [{"symbol": "A"}, {"symbol": "B"}]
    out = logic.reorder(stocks, "A", "A", after=False)
    assert [s["symbol"] for s in out] == ["B", "A"]


# ── sanitize_notes: bozuk Gist verisinde çökme yok ────────────────────────────
def test_sanitize_notes_drops_non_dict_items():
    raw = [{"title": "N1", "body": "b1"}, "bozuk-string", None, 42,
           {"title": "N2"}]
    out = logic.sanitize_notes(raw)
    assert out == [
        {"title": "N1", "body": "b1"},
        {"title": "N2", "body": ""},   # eksik body → boş string
    ]


def test_sanitize_notes_coerces_non_string_fields():
    out = logic.sanitize_notes([{"title": 123, "body": None}])
    assert out == [{"title": "123", "body": "None"}]


def test_sanitize_notes_non_list_returns_empty():
    assert logic.sanitize_notes("değil-liste") == []
    assert logic.sanitize_notes(None) == []


# ── sanitize_stocks: elle bozulan stocks.json'da çökme yok ────────────────────
def test_sanitize_stocks_drops_non_string_symbol():
    # symbol int/None/eksik → group_stocks .startswith AttributeError vermesin
    raw = [
        {"symbol": "THYAO", "entry": 10.0, "exit": 20.0},
        {"symbol": 123},           # int symbol → atılır
        {"symbol": None},          # None symbol → atılır
        {"entry": 5},              # symbol yok → atılır
        {"symbol": "  "},          # boş/whitespace → atılır
        "bozuk-string",            # dict değil → atılır
        {"symbol": "AKBNK"},       # geçerli, entry/exit yok
    ]
    out = logic.sanitize_stocks(raw)
    assert out == [
        {"symbol": "THYAO", "entry": 10.0, "exit": 20.0},
        {"symbol": "AKBNK"},
    ]


def test_sanitize_stocks_coerces_bad_entry_exit_to_none():
    out = logic.sanitize_stocks([{"symbol": "X", "entry": "abc", "exit": None}])
    assert out == [{"symbol": "X", "entry": None, "exit": None}]


def test_sanitize_stocks_rejects_bool_entry():
    # bool int alt-sınıfıdır; fiyat olarak True/False anlamsız → None
    out = logic.sanitize_stocks([{"symbol": "X", "entry": True}])
    assert out == [{"symbol": "X", "entry": None}]


def test_sanitize_stocks_non_list_returns_empty():
    assert logic.sanitize_stocks("değil") == []
    assert logic.sanitize_stocks(None) == []


def test_group_stocks_after_sanitize_no_crash():
    # sanitize_stocks çıktısı group_stocks'u güvenle besler (AttributeError yok)
    raw = [{"symbol": 123}, {"symbol": "THYAO"}]
    groups = logic.group_stocks(logic.sanitize_stocks(raw))
    syms = [s["symbol"] for _, items in groups for s in items]
    assert syms == ["THYAO"]


# ── sanitize_stocks: qty alanı ────────────────────────────────────────────────
def test_sanitize_stocks_keeps_numeric_qty():
    out = logic.sanitize_stocks([{"symbol": "X", "entry": 10.0, "exit": 20.0, "qty": 100}])
    assert out == [{"symbol": "X", "entry": 10.0, "exit": 20.0, "qty": 100}]


def test_sanitize_stocks_coerces_bad_qty_to_none():
    out = logic.sanitize_stocks([{"symbol": "X", "qty": "abc"}])
    assert out == [{"symbol": "X", "qty": None}]
    # bool qty de anlamsız → None
    out2 = logic.sanitize_stocks([{"symbol": "X", "qty": True}])
    assert out2 == [{"symbol": "X", "qty": None}]


def test_sanitize_stocks_qty_absent_not_added():
    # qty anahtarı yoksa çıktıya eklenmez (mevcut kayıtlar bozulmaz)
    out = logic.sanitize_stocks([{"symbol": "X", "entry": 10.0}])
    assert out == [{"symbol": "X", "entry": 10.0}]


# ── compute_pnl: kâr/zarar tutar + yüzde ──────────────────────────────────────
def test_compute_pnl_none_when_missing_entry_or_price():
    assert logic.compute_pnl(None, 100.0, 10) == (None, None)
    assert logic.compute_pnl(100.0, None, 10) == (None, None)


def test_compute_pnl_none_when_entry_zero():
    # entry=0 → sıfıra bölme; güvenli (None, None)
    assert logic.compute_pnl(0, 50.0, 10) == (None, None)


def test_compute_pnl_pct_only_without_qty():
    amount, pct = logic.compute_pnl(100.0, 110.0, None)
    assert amount is None
    assert pct == pytest.approx(10.0)


def test_compute_pnl_amount_with_qty():
    amount, pct = logic.compute_pnl(100.0, 110.0, 50)
    assert amount == pytest.approx(500.0)      # (110-100)*50
    assert pct == pytest.approx(10.0)


def test_compute_pnl_loss_is_negative():
    amount, pct = logic.compute_pnl(100.0, 80.0, 10)
    assert amount == pytest.approx(-200.0)
    assert pct == pytest.approx(-20.0)


def test_compute_pnl_ignores_nonpositive_or_bool_qty():
    # qty <= 0 ya da bool → tutar hesaplanmaz, yüzde durur
    assert logic.compute_pnl(100.0, 110.0, 0)[0] is None
    assert logic.compute_pnl(100.0, 110.0, -5)[0] is None
    assert logic.compute_pnl(100.0, 110.0, True)[0] is None
