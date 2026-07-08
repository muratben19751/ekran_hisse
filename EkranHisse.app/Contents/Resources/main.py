import sys
import os

# Script'in bulunduğu dizini path'e ekle; numpy çakışmasını önle
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
# numpy kaynak ağacı çakışmasını önle
sys.path = [p for p in sys.path if not p.endswith(('numpy', 'numpy/core'))]

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtWidgets import QApplication

from overlay import OverlayWindow


class _AppSignals(QObject):
    data_signal = Signal(list)


def _set_window_level(window):
    try:
        import objc
        ns_view = objc.objc_object(c_void_p=int(window.winId()))
        ns_win = ns_view.window()
        # NSScreenSaverWindowLevel = 1000, biz 1001 yapıyoruz — her şeyin üstü
        ns_win.setLevel_(1001)
        ns_win.setHidesOnDeactivate_(False)
        from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary
        ns_win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary
        )
    except Exception as e:
        print("window level hatası:", e)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    signals = _AppSignals()
    app.data_signal = signals.data_signal

    window = OverlayWindow()
    signals.data_signal.connect(window.apply_data)
    window.show()

    # Başlangıçta ve sonra her 2 saniyede bir level'i yenile
    # (macOS bazı durumlarda sıfırlayabilir)
    QTimer.singleShot(300, lambda: _set_window_level(window))

    keep_top = QTimer()
    keep_top.timeout.connect(lambda: _set_window_level(window))
    keep_top.start(200)  # 200ms'de bir yenile
    app._keep_top = keep_top  # garbage collection'dan koru

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
