import sys
import os
import fcntl
import atexit

# Script'in bulunduğu dizini path'e ekle; numpy çakışmasını önle
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from applog import log

# Tek instance kilidi
_lock_file = os.path.join(_here, ".ekranhisse.lock")
try:
    _lock_fd = open(_lock_file, "w")
except OSError as e:
    log.error("EkranHisse başlatılamadı: kilit dosyası açılamıyor (%s): %s", _lock_file, e)
    sys.exit(1)
try:
    fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    log.info("EkranHisse zaten çalışıyor.")
    sys.exit(0)

def _cleanup_lock():
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        _lock_fd.close()
        os.unlink(_lock_file)
    except Exception:
        pass

atexit.register(_cleanup_lock)
# numpy kaynak ağacı çakışmasını önle
sys.path = [p for p in sys.path if not p.endswith(('numpy', 'numpy/core'))]

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtWidgets import QApplication

from overlay import OverlayWindow, _set_ns_window_level, _COLLECTION_BEHAVIOR


class _AppSignals(QObject):
    data_signal  = Signal(list)
    notes_signal = Signal(object)  # None veya list
    rsi_signal   = Signal(str, object)  # symbol, {5:x, 15:x, 30:x, 60:x}


def _set_window_level(window):
    _set_ns_window_level(window, level=1001, collection_behavior=_COLLECTION_BEHAVIOR)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signals = _AppSignals()

    window = OverlayWindow(signals)
    signals.data_signal.connect(window.apply_data)
    signals.notes_signal.connect(window.apply_notes)
    signals.rsi_signal.connect(window.apply_rsi)
    window.show()

    # Başlangıçta bir kez ayarla, sonra seyrek yenile
    # (macOS nadiren sıfırlar; 2sn agresif ve sürekli objc köprüsü yükü yaratıyordu)
    QTimer.singleShot(300, lambda: _set_window_level(window))

    keep_top = QTimer()
    keep_top.timeout.connect(lambda: window._floating and _set_window_level(window))
    keep_top.start(15000)
    app._keep_top = keep_top

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
