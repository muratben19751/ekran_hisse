import sys
import os
import fcntl
import atexit

# Script'in bulunduğu dizini path'e ekle; numpy çakışmasını önle
_here = os.path.dirname(os.path.abspath(__file__))

# Tek instance kilidi
_lock_file = os.path.join(_here, ".ekranhisse.lock")
_lock_fd = open(_lock_file, "w")
try:
    fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("EkranHisse zaten çalışıyor.")
    sys.exit(0)

def _cleanup_lock():
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        _lock_fd.close()
        os.unlink(_lock_file)
    except Exception:
        pass

atexit.register(_cleanup_lock)
if _here not in sys.path:
    sys.path.insert(0, _here)
# numpy kaynak ağacı çakışmasını önle
sys.path = [p for p in sys.path if not p.endswith(('numpy', 'numpy/core'))]

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtWidgets import QApplication

from overlay import OverlayWindow


class _AppSignals(QObject):
    data_signal  = Signal(list)
    notes_signal = Signal(object)  # None veya list


try:
    from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary
    _COLLECTION_BEHAVIOR = NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
except Exception:
    _COLLECTION_BEHAVIOR = None


def _set_window_level(window):
    try:
        import objc
        ns_view = objc.objc_object(c_void_p=int(window.winId()))
        ns_win = ns_view.window()
        ns_win.setLevel_(1001)
        ns_win.setHidesOnDeactivate_(False)
        if _COLLECTION_BEHAVIOR is not None:
            ns_win.setCollectionBehavior_(_COLLECTION_BEHAVIOR)
    except Exception as e:
        print("window level hatası:", e)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signals = _AppSignals()
    app.data_signal  = signals.data_signal
    app.notes_signal = signals.notes_signal

    window = OverlayWindow()
    signals.data_signal.connect(window.apply_data)
    signals.notes_signal.connect(window.apply_notes)
    window.show()

    # Başlangıçta ve sonra her 2 saniyede bir level'i yenile
    # (macOS bazı durumlarda sıfırlayabilir)
    QTimer.singleShot(300, lambda: _set_window_level(window))

    keep_top = QTimer()
    keep_top.timeout.connect(lambda: _set_window_level(window))
    keep_top.start(2000)
    app._keep_top = keep_top

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
