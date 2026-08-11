"""EkranHisse — merkezî loglama.

.app bundle olarak çalışırken stdout hiçbir yere düşmez; bu yüzden hem konsola
hem de ~/Library/Logs/EkranHisse.log dosyasına yazan tek bir logger sağlar.
Tüm modüller `from applog import log` ile aynı logger'ı kullanır.
"""

import logging
import os

_LOG_PATH = os.path.expanduser("~/Library/Logs/EkranHisse.log")

log = logging.getLogger("ekranhisse")

if not log.handlers:
    log.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    _stream = logging.StreamHandler()
    _stream.setFormatter(_fmt)
    log.addHandler(_stream)

    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        _file = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        _file.setFormatter(_fmt)
        log.addHandler(_file)
    except OSError:
        # Dosya açılamazsa (izin/salt-okunur) sessizce yalnızca konsola yaz.
        pass

    log.propagate = False
