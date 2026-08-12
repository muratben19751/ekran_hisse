"""load_stocks / save_stocks / load_tw_symbols / save_tw_symbols testleri.

overlay.py PySide6'ya bağlı; yüklüyse test çalışır, değilse tüm modül atlanır.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

overlay = pytest.importorskip("overlay")   # PySide6 yoksa atla
import paths  # noqa: E402  (overlay importundan sonra; yol politikası tek yerde)


@pytest.fixture(autouse=True)
def _no_legacy_migration(tmp_path, monkeypatch):
    """load_* fonksiyonları eski kaynak-dizini dosyasını migrate eder; testlerde
    gerçek stocks.json/tw_symbols.json'a dokunmasın diye legacy yollarını
    var olmayan bir tmp konuma sabitle."""
    monkeypatch.setattr(overlay, "_LEGACY_STOCKS", str(tmp_path / "legacy_stocks.json"))
    monkeypatch.setattr(overlay, "_LEGACY_TW", str(tmp_path / "legacy_tw.json"))


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


# ── migrasyon: eski kaynak-dizini dosyası → ~/.ekranhisse ────────────────────
def test_load_stocks_migrates_legacy(tmp_path, monkeypatch):
    user = str(tmp_path / "stocks.json")           # ~/.ekranhisse konumu (yok)
    legacy = str(tmp_path / "legacy_stocks.json")  # eski kaynak-dizini konumu
    monkeypatch.setattr(overlay, "STOCKS_FILE", user)
    monkeypatch.setattr(overlay, "_LEGACY_STOCKS", legacy)
    with open(legacy, "w") as fh:
        json.dump([{"symbol": "THYAO", "entry": 1.0, "exit": 2.0}], fh)
    result = overlay.load_stocks()
    assert result == [{"symbol": "THYAO", "entry": 1.0, "exit": 2.0}]
    assert os.path.exists(user)   # kullanıcı dizinine kopyalandı


def test_load_stocks_no_migration_when_user_exists(tmp_path, monkeypatch):
    user = str(tmp_path / "stocks.json")
    legacy = str(tmp_path / "legacy_stocks.json")
    monkeypatch.setattr(overlay, "STOCKS_FILE", user)
    monkeypatch.setattr(overlay, "_LEGACY_STOCKS", legacy)
    with open(user, "w") as fh:
        json.dump([{"symbol": "AKBNK"}], fh)
    with open(legacy, "w") as fh:
        json.dump([{"symbol": "THYAO"}], fh)   # ezilmemeli
    assert overlay.load_stocks() == [{"symbol": "AKBNK"}]


# ── _save_json: atomik yazma + hata yolu (en kritik kalıcılık kodu) ──────────
def test_save_json_atomic_roundtrip(tmp_path, monkeypatch):
    f = str(tmp_path / "out.json")
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    overlay._save_json(f, [{"symbol": "X"}])
    with open(f, encoding="utf-8") as fh:
        assert json.load(fh) == [{"symbol": "X"}]


def test_save_json_no_tmp_file_left_behind(tmp_path, monkeypatch):
    f = str(tmp_path / "out.json")
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    overlay._save_json(f, {"a": 1})
    leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
    assert leftovers == []


def test_save_json_failure_preserves_existing_file(tmp_path, monkeypatch):
    # Atomikliğin asıl amacı: yazma başarısızlığında mevcut dosya BOZULMAZ.
    f = str(tmp_path / "out.json")
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    overlay._save_json(f, [{"symbol": "SAĞLAM"}])   # önce geçerli içerik
    # json.dump'ı patlat: serialize edilemeyen nesne ver → OSError değil TypeError,
    # bu yüzden dir'i yazılamaz yaparak OSError tetikle.
    ro = tmp_path / "ro"
    ro.mkdir()
    target = str(ro / "x.json")
    overlay._save_json(target, [{"symbol": "İLK"}])   # ro içinde ilk yazım
    os.chmod(ro, 0o500)   # salt-okunur dizin
    try:
        overlay._save_warned.discard(target)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            overlay._save_json(target, [{"symbol": "YENİ"}])   # yazamaz
        # Eski içerik korunmalı (kısmi/bozuk yazım yok)
        with open(target, encoding="utf-8") as fh:
            assert json.load(fh) == [{"symbol": "İLK"}]
    finally:
        os.chmod(ro, 0o700)


def test_save_json_warns_once(tmp_path, monkeypatch, recwarn):
    ro = tmp_path / "ro2"
    ro.mkdir()
    target = str(ro / "y.json")
    monkeypatch.setattr(paths, "DATA_DIR", str(ro))
    os.chmod(ro, 0o500)
    try:
        overlay._save_warned.discard(target)
        overlay._save_json(target, [1])
        overlay._save_json(target, [2])   # ikinci hata — tekrar uyarmamalı
        warns = [w for w in recwarn.list if "yazılamadı" in str(w.message)]
        assert len(warns) == 1
    finally:
        os.chmod(ro, 0o700)
        overlay._save_warned.discard(target)


# ── load_tw_symbols: normalizasyon (upper + string-olmayan filtre) ───────────
def test_load_tw_symbols_uppercases(tmp_path, monkeypatch):
    f = str(tmp_path / "tw.json")
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", f)
    with open(f, "w") as fh:
        json.dump(["ttkom", "AkBnk"], fh)
    assert overlay.load_tw_symbols() == ["TTKOM", "AKBNK"]


def test_load_tw_symbols_drops_non_strings_and_empties(tmp_path, monkeypatch):
    f = str(tmp_path / "tw.json")
    monkeypatch.setattr(overlay, "TW_SYMBOLS_FILE", f)
    with open(f, "w") as fh:
        json.dump(["THYAO", 123, None, "  ", "", "garan"], fh)
    assert overlay.load_tw_symbols() == ["THYAO", "GARAN"]
