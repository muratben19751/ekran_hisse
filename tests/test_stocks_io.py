"""load_stocks / save_stocks / load_tw_symbols / save_tw_symbols testleri.

overlay.py PySide6'ya bağlı; yüklüyse test çalışır, değilse tüm modül atlanır.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

overlay = pytest.importorskip("overlay")   # PySide6 yoksa atla


# ── load_stocks ──────────────────────────────────────────────────────────────
def test_load_stocks_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(overlay, "STOCKS_FILE", str(tmp_path / "yok.json"))
    assert overlay.load_stocks() == []


def test_load_stocks_roundtrip(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    data = [{"symbol": "THYAO", "entry": 10.0, "exit": 20.0}]
    overlay.save_stocks(data)
    assert overlay.load_stocks() == data


def test_load_stocks_old_format_migration(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    with open(f, "w") as fh:
        json.dump(["THYAO", "AKBNK"], fh)
    result = overlay.load_stocks()
    assert result == [
        {"symbol": "THYAO", "entry": None, "exit": None},
        {"symbol": "AKBNK", "entry": None, "exit": None},
    ]


def test_load_stocks_corrupt_json(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    with open(f, "w") as fh:
        fh.write("{ bozuk json ]")
    assert overlay.load_stocks() == []   # çökmemeli


def test_load_stocks_empty_file(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    open(f, "w").close()
    assert overlay.load_stocks() == []


def test_load_stocks_dict_not_list(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    with open(f, "w") as fh:
        json.dump({"x": 1}, fh)
    assert overlay.load_stocks() == []   # KeyError yerine boş liste


def test_load_stocks_drops_records_without_symbol(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    with open(f, "w") as fh:
        json.dump([{"symbol": "THYAO"}, {"entry": 5}], fh)
    result = overlay.load_stocks()
    assert result == [{"symbol": "THYAO"}]


def test_save_stocks_turkish_chars(tmp_path, monkeypatch):
    f = str(tmp_path / "stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", f)
    overlay.save_stocks([{"symbol": "---:Şirketler:0"}])
    with open(f, encoding="utf-8") as fh:
        content = fh.read()
    assert "Şirketler" in content   # ensure_ascii=False


# ── load_tw_symbols / save_tw_symbols ────────────────────────────────────────
def test_load_tw_symbols_default(tmp_path, monkeypatch):
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", str(tmp_path / "yok.json"))
    assert overlay.load_tw_symbols() == ["TTKOM"]


def test_tw_symbols_roundtrip(tmp_path, monkeypatch):
    f = str(tmp_path / "tw.json")
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", f)
    overlay.save_tw_symbols(["TTKOM", "AKBNK"])
    assert overlay.load_tw_symbols() == ["TTKOM", "AKBNK"]


def test_load_tw_symbols_corrupt_falls_back(tmp_path, monkeypatch):
    f = str(tmp_path / "tw.json")
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", f)
    with open(f, "w") as fh:
        fh.write("bozuk")
    assert overlay.load_tw_symbols() == ["TTKOM"]


def test_load_tw_symbols_empty_list_falls_back(tmp_path, monkeypatch):
    f = str(tmp_path / "tw.json")
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", f)
    with open(f, "w") as fh:
        json.dump([], fh)
    assert overlay.load_tw_symbols() == ["TTKOM"]
