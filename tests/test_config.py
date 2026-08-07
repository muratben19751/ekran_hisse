"""config.py — env dosyası okuma testleri."""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _reload_config(cfg_path):
    """config modülünü verilen dosya yoluyla yeniden yükle."""
    import config as cfg_mod
    cfg_mod._CFG_FILE = cfg_path
    cfg_mod._CFG = cfg_mod._load()
    return cfg_mod


# ── _load ────────────────────────────────────────────────────────────────────
def test_load_missing_file(tmp_path):
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(tmp_path / "yok.env")
    assert cfg_mod._load() == {}


def test_load_basic_key_value(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("GIST_ID=abc123\nGITHUB_TOKEN=tok\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load()
    assert cfg["GIST_ID"] == "abc123"
    assert cfg["GITHUB_TOKEN"] == "tok"


def test_load_ignores_comments(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("# bu yorum\nGIST_ID=xyz\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load()
    assert "# bu yorum" not in cfg
    assert cfg["GIST_ID"] == "xyz"


def test_load_ignores_lines_without_equals(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("SADECE_ANAHTAR\nGIST_ID=abc\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load()
    assert "SADECE_ANAHTAR" not in cfg
    assert cfg["GIST_ID"] == "abc"


def test_load_strips_whitespace(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("  GIST_ID  =  abc123  \n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load()
    assert cfg["GIST_ID"] == "abc123"


def test_load_value_with_equals_sign(tmp_path):
    # Değerin içinde '=' olabilir (ör. JWT token)
    f = tmp_path / "cfg.env"
    f.write_text("TOKEN=abc=def=ghi\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load()
    assert cfg["TOKEN"] == "abc=def=ghi"


def test_load_empty_file(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    assert cfg_mod._load() == {}


# ── get ──────────────────────────────────────────────────────────────────────
def test_get_existing_key(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("GIST_ID=mygist\n")
    cfg_mod = _reload_config(str(f))
    assert cfg_mod.get("GIST_ID") == "mygist"


def test_get_missing_key_returns_default(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("")
    cfg_mod = _reload_config(str(f))
    assert cfg_mod.get("YOK_ANAHTAR") == ""
    assert cfg_mod.get("YOK_ANAHTAR", "varsayilan") == "varsayilan"


# ── ~/.ekranhisse/ yolu önceliği ─────────────────────────────────────────────
def test_user_cfg_takes_priority_over_local(tmp_path, monkeypatch):
    user_dir = tmp_path / ".ekranhisse"
    user_dir.mkdir()
    user_cfg = user_dir / "notes_config.env"
    user_cfg.write_text("GIST_ID=user_gist\n")

    local_cfg = tmp_path / "notes_config.env"
    local_cfg.write_text("GIST_ID=local_gist\n")

    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_USER_CFG", str(user_cfg))
    monkeypatch.setattr(cfg_mod, "_CFG_FILE", str(user_cfg))
    cfg_mod._CFG = cfg_mod._load()

    assert cfg_mod.get("GIST_ID") == "user_gist"


def test_local_cfg_used_when_user_missing(tmp_path, monkeypatch):
    local_cfg = tmp_path / "notes_config.env"
    local_cfg.write_text("GIST_ID=local_gist\n")

    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_USER_CFG", str(tmp_path / "yok.env"))
    monkeypatch.setattr(cfg_mod, "_CFG_FILE", str(local_cfg))
    cfg_mod._CFG = cfg_mod._load()

    assert cfg_mod.get("GIST_ID") == "local_gist"
