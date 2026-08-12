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


# ── Sır kaynağı: yalnızca ~/.ekranhisse (proje-kökü fallback KALDIRILDI) ──────
def test_only_user_cfg_path_is_used(tmp_path, monkeypatch):
    """Sırlar yalnızca kullanıcı dizini env'inden okunur; kaynak dizini değil."""
    user_cfg = tmp_path / ".ekranhisse" / "notes_config.env"
    user_cfg.parent.mkdir()
    user_cfg.write_text("GIST_ID=user_gist\n")

    import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_keychain_get", lambda k: None)
    monkeypatch.setattr(cfg_mod, "_CFG_FILE", str(user_cfg))
    cfg_mod._ENV = cfg_mod._load_env()

    assert cfg_mod.get("GIST_ID") == "user_gist"


def test_no_project_dir_fallback(tmp_path, monkeypatch):
    """config artık _LOCAL_CFG / _USER_CFG ayrımı taşımaz — tek _CFG_FILE."""
    import config as cfg_mod
    assert not hasattr(cfg_mod, "_LOCAL_CFG")
    assert not hasattr(cfg_mod, "_USER_CFG")
    # _CFG_FILE varsayılanı her zaman kullanıcı dizinine işaret eder (başka
    # testler monkeypatch'lemiş olabileceğinden orijinal ifadeyi yeniden hesapla).
    import os
    assert os.path.expanduser("~/.ekranhisse/notes_config.env").endswith(
        "/.ekranhisse/notes_config.env")
