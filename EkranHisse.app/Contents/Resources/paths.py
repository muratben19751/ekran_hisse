"""EkranHisse — kalıcı kullanıcı verisi için tek yol politikası.

Portföy/sembol/kilit/sır dosyalarının kök dizini burada TEK YERDE tanımlıdır.
Eskiden ~/.ekranhisse üç modülde (main.py, config.py, overlay.py) bağımsız
hardcode ediliyordu ve ensure_data_dir mantığı iki yerde birbirinden farklı
davranıyordu (biri OSError'da home'a düşüyor, diğeri sadece log'luyordu). Yol
politikası değişirse tek bu dosyayı güncellemek yeter.

.app bundle Resources dizini salt-okunur olabilir (Gatekeeper App
Translocation, imzalı/notarize bundle); bu yüzden veri her zaman yazılabilir
kullanıcı dizinine yazılır.
"""

import os

from applog import log

_DEFAULT_DIR = os.path.expanduser("~/.ekranhisse")
_HOME = os.path.expanduser("~")

# Tek gerçek kaynak. ensure_data_dir() OSError'da bunu _HOME'a düşürebilir.
DATA_DIR = _DEFAULT_DIR


def ensure_data_dir() -> str:
    """Veri dizinini oluştur; oluşturulamazsa son çare olarak ~ kullan.

    Döndürür: kullanılabilir DATA_DIR (fallback sonrası). Tüm modüller yol
    üretimi için data_file()/DATA_DIR kullanmalı, kendi makedirs'ini yazmamalı.
    """
    global DATA_DIR
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError as e:
        log.warning("veri dizini oluşturulamadı (%s): %s — ~ kullanılıyor", DATA_DIR, e)
        DATA_DIR = _HOME
    return DATA_DIR


def data_file(name: str) -> str:
    """DATA_DIR altındaki bir dosyanın tam yolu (dizini oluşturmaz)."""
    return os.path.join(DATA_DIR, name)
