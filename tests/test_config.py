"""config.py — env dosyası okuma + Keychain önceliği testleri."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _reload_config_env(cfg_mod, cfg_path):
    """config modülünü verilen env dosya yoluyla yeniden yükle."""
    cfg_mod._CFG_FILE = cfg_path
    cfg_mod._ENV = cfg_mod._load_env()
    return cfg_mod


# ── _load_env ─────────────────────────────────────────────────────────────────
def test_load_missing_file(tmp_path):
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(tmp_path / "yok.env")
    assert cfg_mod._load_env() == {}


def test_load_basic_key_value(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("GIST_ID=abc123\nGITHUB_TOKEN=tok\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load_env()
    assert cfg["GIST_ID"] == "abc123"
    assert cfg["GITHUB_TOKEN"] == "tok"


def test_load_ignores_comments(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("# bu yorum\nGIST_ID=xyz\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load_env()
    assert "# bu yorum" not in cfg
    assert cfg["GIST_ID"] == "xyz"


def test_load_ignores_lines_without_equals(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("SADECE_ANAHTAR\nGIST_ID=abc\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load_env()
    assert "SADECE_ANAHTAR" not in cfg
    assert cfg["GIST_ID"] == "abc"


def test_load_strips_whitespace(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("  GIST_ID  =  abc123  \n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load_env()
    assert cfg["GIST_ID"] == "abc123"


def test_load_value_with_equals_sign(tmp_path):
    # Değerin içinde '=' olabilir (ör. JWT token)
    f = tmp_path / "cfg.env"
    f.write_text("TOKEN=abc=def=ghi\n")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    cfg = cfg_mod._load_env()
    assert cfg["TOKEN"] == "abc=def=ghi"


def test_load_empty_file(tmp_path):
    f = tmp_path / "cfg.env"
    f.write_text("")
    import config as cfg_mod
    cfg_mod._CFG_FILE = str(f)
    assert cfg_mod._load_env() == {}


# ── get (Keychain devre dışıyken env'e düşer) ─────────────────────────────────
def test_get_existing_key(tmp_path, monkeypatch):
    f = tmp_path / "cfg.env"
    f.write_text("GIST_ID=mygist\n")
    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get", lambda k: None)
    _reload_config_env(cfg_mod, str(f))
    assert cfg_mod.get("GIST_ID") == "mygist"


def test_get_missing_key_returns_default(tmp_path, monkeypatch):
    f = tmp_path / "cfg.env"
    f.write_text("")
    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get", lambda k: None)
    _reload_config_env(cfg_mod, str(f))
    assert cfg_mod.get("YOK_ANAHTAR") == ""
    assert cfg_mod.get("YOK_ANAHTAR", "varsayilan") == "varsayilan"


def test_keychain_takes_priority_over_env(tmp_path, monkeypatch):
    """Keychain değeri varsa env dosyası ezilir (güvenli kaynak önce)."""
    f = tmp_path / "cfg.env"
    f.write_text("GITHUB_TOKEN=env_token\n")
    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get",
                        lambda k: "kc_token" if k == "GITHUB_TOKEN" else None)
    _reload_config_env(cfg_mod, str(f))
    assert cfg_mod.get("GITHUB_TOKEN") == "kc_token"


# ── ~/.ekranhisse/ yolu önceliği ─────────────────────────────────────────────
def test_user_cfg_takes_priority_over_local(tmp_path, monkeypatch):
    user_dir = tmp_path / ".ekranhisse"
    user_dir.mkdir()
    user_cfg = user_dir / "notes_config.env"
    user_cfg.write_text("GIST_ID=user_gist\n")

    local_cfg = tmp_path / "notes_config.env"
    local_cfg.write_text("GIST_ID=local_gist\n")

    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get", lambda k: None)
    monkeypatch.setattr(cfg_mod, "_USER_CFG", str(user_cfg))
    monkeypatch.setattr(cfg_mod, "_CFG_FILE", str(user_cfg))
    cfg_mod._ENV = cfg_mod._load_env()

    assert cfg_mod.get("GIST_ID") == "user_gist"


def test_local_cfg_used_when_user_missing(tmp_path, monkeypatch):
    local_cfg = tmp_path / "notes_config.env"
    local_cfg.write_text("GIST_ID=local_gist\n")

    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get", lambda k: None)
    monkeypatch.setattr(cfg_mod, "_USER_CFG", str(tmp_path / "yok.env"))
    monkeypatch.setattr(cfg_mod, "_CFG_FILE", str(local_cfg))
    cfg_mod._ENV = cfg_mod._load_env()

    assert cfg_mod.get("GIST_ID") == "local_gist"
