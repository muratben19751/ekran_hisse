"""paths.py — tek yol politikası + OSError fallback testleri."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paths


# ── data_file ─────────────────────────────────────────────────────────────────
def test_data_file_joins_under_data_dir(monkeypatch):
    # data_file(name), DATA_DIR altındaki tam yolu üretir (dizin oluşturmaz).
    monkeypatch.setattr(paths, "DATA_DIR", "/tmp/ekranhisse_test")
    assert paths.data_file("stocks.json") == "/tmp/ekranhisse_test/stocks.json"


# ── ensure_data_dir: normal yol ───────────────────────────────────────────────
def test_ensure_data_dir_creates_and_returns(monkeypatch, tmp_path):
    # makedirs başarılıysa DATA_DIR aynen döner (fallback yok).
    target = str(tmp_path / "veri")
    monkeypatch.setattr(paths, "DATA_DIR", target)
    made = {}

    def fake_makedirs(path, exist_ok=False):
        made["path"] = path

    monkeypatch.setattr(paths.os, "makedirs", fake_makedirs)
    result = paths.ensure_data_dir()
    assert result == target
    assert made["path"] == target
    assert paths.DATA_DIR == target


# ── ensure_data_dir: OSError fallback → _HOME ─────────────────────────────────
def test_ensure_data_dir_oserror_falls_back_to_home(monkeypatch):
    # makedirs OSError fırlatırsa (salt-okunur/izin) DATA_DIR _HOME'a düşer ve
    # o değer döner; süreç yine yazılabilir bir dizine sahip olur.
    monkeypatch.setattr(paths, "DATA_DIR", "/olmayan/salt_okunur/dizin")

    def boom(path, exist_ok=False):
        raise OSError("izin yok / salt-okunur")

    monkeypatch.setattr(paths.os, "makedirs", boom)
    result = paths.ensure_data_dir()
    assert result == paths._HOME
    assert paths.DATA_DIR == paths._HOME
