"""logic.py — saf iş mantığı birim testleri."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic


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
