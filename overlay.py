"""EkranHisse — Yoğun HUD overlay penceresi."""

import json
import math
import os
import subprocess
import tempfile
import threading
from datetime import datetime

try:
    from AppKit import NSEvent as _NSEvent
    from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces as _CB_ALL_SPACES
    from AppKit import NSWindowCollectionBehaviorStationary as _CB_STATIONARY
    _APPKIT_OK = True
    _COLLECTION_BEHAVIOR = _CB_ALL_SPACES | _CB_STATIONARY
except Exception:
    _APPKIT_OK = False
    _COLLECTION_BEHAVIOR = None

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QMimeData,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
import paths
import symbols as sym_universe
import twitter_client
from applog import log
from data_fetcher import fetch_all, fetch_tv_rsi_bulk
from logic import (
    _SEP_SYMBOL,
    compute_unread,
    group_stocks,
    make_sep_symbol,
    next_separator_counter,
    parse_price,
    parse_sep_symbol,
    reorder,
    sanitize_notes,
    sanitize_stocks,
    symbols_of_tweet,
    tr_number,
    tw_ago,
    twitter_query,
)
from notes_api_client import fetch_notes, save_notes

# ── Kalıcı kullanıcı verisi ~/.ekranhisse altında ────────────────────────────
# Portföy ve takip sembolleri kullanıcı verisidir; sırlar/notlar gibi kullanıcı
# dizininde tutulur. .app bundle salt-okunur/güncellemede ezilebilir olduğundan
# kod dizinine YAZILMAZ. Eski konumdaki (kaynak dizini) dosyalar ilk çalıştırmada
# bir kez migrate edilir. Yol politikası tek yerde: paths modülü.
_LEGACY_DIR = os.path.dirname(os.path.abspath(__file__))
STOCKS_FILE = paths.data_file("stocks.json")
TW_SYMBOLS_FILE = paths.data_file("tw_symbols.json")
_LEGACY_STOCKS = os.path.join(_LEGACY_DIR, "stocks.json")
_LEGACY_TW = os.path.join(_LEGACY_DIR, "tw_symbols.json")
REFRESH_INTERVAL_MS = 60_000


def _ensure_data_dir():
    # Ortak politika: paths.ensure_data_dir (makedirs + OSError'da ~ fallback).
    paths.ensure_data_dir()


def _migrate_legacy(user_path, legacy_path):
    """Eski kaynak-dizini dosyasını bir kez kullanıcı dizinine taşı."""
    if os.path.exists(user_path) or not os.path.exists(legacy_path):
        return
    _ensure_data_dir()
    try:
        with open(legacy_path, encoding="utf-8") as src:
            content = src.read()
        with open(user_path, "w", encoding="utf-8") as dst:
            dst.write(content)
        log.info("kullanıcı verisi taşındı: %s → %s", legacy_path, user_path)
    except OSError as e:
        log.warning("veri taşınamadı (%s → %s): %s", legacy_path, user_path, e)

# ── Geometri ────────────────────────────────────────────────────────────────
PANEL_W = 300
TAB_W   = 32
TAB_H   = 52
TAB_GAP = 6
ANIM_MS = 120

R_PANEL  = 12
R_CARD   = 10
R_BTN    = 7
R_TAB    = 9

# ── Renkler (tasarım 1b) ────────────────────────────────────────────────────
C_PANEL_BG   = "rgba(30, 30, 32, 236)"
C_BORDER     = "rgba(255, 255, 255, 30)"
C_CARD       = "rgba(255, 255, 255, 18)"
C_ROW_HOVER  = "rgba(255, 255, 255, 14)"
C_HAIRLINE   = "rgba(255, 255, 255, 18)"
C_CTRL       = "rgba(255, 255, 255, 28)"
C_CTRL_HOVER = "rgba(255, 255, 255, 46)"
C_FIELD      = "rgba(255, 255, 255, 23)"
C_EDITOR_BG  = "rgba(0, 0, 0, 56)"

C_TEXT   = "#ffffff"
C_TEXT2  = "rgba(235, 235, 245, 190)"
C_TEXT3  = "rgba(235, 235, 245, 128)"
C_TEXT4  = "rgba(235, 235, 245, 88)"

C_GREEN     = "#30d158"
C_GREEN_INK = "#06280f"
C_RED       = "#ff453a"
C_RED_INK   = "#2b0603"
C_BLUE      = "#0a84ff"
C_BLUE_HOVER = "#3d9bff"
C_YELLOW    = "#ffd60a"
C_SHEET_BG  = "rgba(44, 44, 46, 246)"
C_TINT_TGT  = "rgba(255, 214, 10, 20)"
C_TINT_NEW  = "rgba(10, 132, 255, 20)"

MIME_ROW = "application/x-ekranhisse-symbol"


# ── Yardımcılar ─────────────────────────────────────────────────────────────
_font_cache: dict = {}

def _f(size, weight=QFont.Normal):
    key = (size, weight)
    f = _font_cache.get(key)
    if f is None:
        f = QFont()
        f.setPointSize(size)
        f.setWeight(weight)
        _font_cache[key] = f
    return f


# Geriye dönük uyumlu takma adlar — asıl mantık logic.py'da.
_tr = tr_number
_parse_price = parse_price
_parse_sep_symbol = parse_sep_symbol
_tw_ago = tw_ago


def _main_screen():
    return QApplication.primaryScreen().geometry()


def _set_ns_window_level(win, level: int = 1001, collection_behavior=None, make_key: bool = False):
    """macOS NSWindow seviyesini ve davranışını ayarla. macOS dışında no-op."""
    try:
        import objc
        ns_view = objc.objc_object(c_void_p=int(win.winId()))
        ns_win = ns_view.window()
        ns_win.setLevel_(level)
        ns_win.setHidesOnDeactivate_(False)
        if collection_behavior is not None:
            ns_win.setCollectionBehavior_(collection_behavior)
        if make_key:
            ns_win.makeKeyAndOrderFront_(None)
    except Exception as e:
        log.warning("_set_ns_window_level: %s", e)


_save_warned = set()


def _save_json(path, data):
    """JSON'u atomik yaz (tempfile + os.replace). Hata bir kez uyarılır."""
    tmp = None
    try:
        _ensure_data_dir()
        dir_ = os.path.dirname(path)
        with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False,
                                         suffix=".tmp", encoding="utf-8") as f:
            tmp = f.name
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
        _save_warned.discard(path)
    except OSError as e:
        if path not in _save_warned:
            _save_warned.add(path)
            import warnings
            warnings.warn(f"_save_json: {path} yazılamadı: {e}", stacklevel=2)
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def load_stocks():
    _migrate_legacy(STOCKS_FILE, _LEGACY_STOCKS)
    if not os.path.exists(STOCKS_FILE):
        return []
    try:
        with open(STOCKS_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    if data and isinstance(data[0], str):
        return [{"symbol": s, "entry": None, "exit": None} for s in data]
    # Bozuk/elle düzenlenmiş kayıtları ele: symbol'ü boş-olmayan string olmayan
    # kayıtlar group_stocks/reorder içinde AttributeError ile UI'ı çökertmesin.
    return sanitize_stocks(data)


def save_stocks(stocks):
    _save_json(STOCKS_FILE, stocks)


def load_tw_symbols():
    """𝕏 takip sembolleri; dosya yoksa/bozuksa varsayılan ['TTKOM']."""
    _migrate_legacy(TW_SYMBOLS_FILE, _LEGACY_TW)
    if not os.path.exists(TW_SYMBOLS_FILE):
        return ["TTKOM"]
    try:
        with open(TW_SYMBOLS_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ["TTKOM"]
    if not isinstance(data, list):
        return ["TTKOM"]
    syms = [str(s).upper() for s in data if isinstance(s, str) and s.strip()]
    return syms or ["TTKOM"]


def save_tw_symbols(symbols):
    _save_json(TW_SYMBOLS_FILE, symbols)


def _pill(text, primary=False, width=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFont(_f(12, QFont.Medium))
    b.setFixedHeight(24)
    if width:
        b.setFixedWidth(width)
    bg   = C_BLUE if primary else C_CTRL
    hov  = C_BLUE_HOVER if primary else C_CTRL_HOVER
    fg   = "#ffffff" if primary else C_TEXT2
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: {fg}; border: none;"
        f" border-radius: {R_BTN}px; padding: 0 12px; }}"
        f"QPushButton:hover {{ background: {hov}; color: #ffffff; }}"
    )
    return b


def _flat(text, color=None):
    """Yoğun görünüm için çerçevesiz metin butonu."""
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFont(_f(11))
    b.setFixedHeight(18)
    b.setStyleSheet(
        f"QPushButton {{ background: transparent; border: none; padding: 0 2px;"
        f" color: {color or C_TEXT3}; text-align: left; }}"
        f"QPushButton:hover {{ color: {color or C_TEXT}; }}"
    )
    return b


def _menu(parent):
    m = QMenu(parent)
    m.setFont(_f(12))
    m.setStyleSheet(
        f"QMenu {{ background: {C_SHEET_BG}; color: {C_TEXT};"
        f" border: 1px solid {C_BORDER}; border-radius: 9px; padding: 4px; }}"
        "QMenu::item { padding: 5px 12px; border-radius: 6px; }"
        f"QMenu::item:selected {{ background: {C_BLUE}; color: #ffffff; }}"
        f"QMenu::separator {{ height: 1px; background: {C_HAIRLINE}; margin: 4px 8px; }}"
    )
    return m


def _hairline():
    ln = QFrame()
    ln.setFixedHeight(1)
    ln.setStyleSheet(f"background: {C_HAIRLINE}; margin-left: 12px;")
    return ln


# ── Diyaloglar ──────────────────────────────────────────────────────────────
class _SheetDialog(QDialog):
    """Panele bitişik, macOS sheet görünümlü frameless diyalog."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background: transparent; }")
        self.box = QWidget(self)
        self.box.setObjectName("sheet")
        self.box.setStyleSheet(
            f"#sheet {{ background: {C_SHEET_BG}; border: 1px solid {C_BORDER};"
            f" border-radius: {R_PANEL}px; }}"
        )
        self.lay = QVBoxLayout(self.box)
        self.lay.setContentsMargins(14, 14, 14, 14)
        self.lay.setSpacing(12)

    def _field(self, caption, value=""):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(5)
        cap = QLabel(caption)
        cap.setFont(_f(11))
        cap.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        inp = QLineEdit(value)
        inp.setFont(_f(13))
        inp.setFixedHeight(26)
        inp.setStyleSheet(
            f"QLineEdit {{ background: {C_FIELD}; border: 1px solid {C_BORDER};"
            f" border-radius: {R_BTN}px; color: {C_TEXT}; padding: 0 9px; }}"
            f"QLineEdit:focus {{ border-color: {C_BLUE}; }}"
        )
        v.addWidget(cap)
        v.addWidget(inp)
        return wrap, inp

    def _place(self, w, h):
        sc = QApplication.primaryScreen().availableGeometry()
        self.box.setGeometry(0, 0, w, h)
        self.resize(w, h)
        x = sc.x() + sc.width() - TAB_W - PANEL_W - w - 8
        y = sc.y() + (sc.height() - h) // 2
        self.move(x, y)
        QTimer.singleShot(0, lambda: _set_ns_window_level(self, level=1002, make_key=True))


class TextSheet(_SheetDialog):
    """Tek satır giriş (sembol ekle / bölüm adı)."""

    def __init__(self, title, caption, default="", parent=None):
        super().__init__(parent)
        head = QLabel(title)
        head.setFont(_f(13, QFont.DemiBold))
        head.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        self.lay.addWidget(head)

        wrap, self.inp = self._field(caption, default)
        self.inp.selectAll()
        self.lay.addWidget(wrap)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addStretch()
        cancel = _pill("İptal")
        ok = _pill("Kaydet", primary=True)
        bar.addWidget(cancel)
        bar.addWidget(ok)
        self.lay.addLayout(bar)

        self.value = None
        ok.clicked.connect(self._ok)
        self.inp.returnPressed.connect(self._ok)
        cancel.clicked.connect(self.reject)
        self._place(248, 128)

    def _ok(self):
        val = self.inp.text().strip()
        if not val:
            return
        self.value = val
        self.accept()


# Sembol evreni tek kaynaktan (symbols.json) gelir.
_BIST_SYMBOLS = sym_universe.KNOWN


class StockPickerSheet(_SheetDialog):
    """Hisse ekleme — yazarken filtreli liste."""

    def __init__(self, existing=None, parent=None):
        super().__init__(parent)
        self._existing = {s.upper() for s in (existing or [])}
        self.value = None

        head = QLabel("Hisse ekle")
        head.setFont(_f(13, QFont.DemiBold))
        head.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        self.lay.addWidget(head)

        self.inp = QLineEdit()
        self.inp.setFont(_f(13))
        self.inp.setFixedHeight(28)
        self.inp.setPlaceholderText("Sembol yaz… (örn. THYAO)")
        self.inp.setStyleSheet(
            f"QLineEdit {{ background: {C_FIELD}; border: 1px solid {C_BORDER};"
            f" border-radius: {R_BTN}px; color: {C_TEXT}; padding: 0 9px; }}"
            f"QLineEdit:focus {{ border-color: {C_BLUE}; }}"
        )
        self.lay.addWidget(self.inp)

        self.lst = QListWidget()
        self.lst.setFixedHeight(160)
        self.lst.setFont(_f(12))
        self.lst.setStyleSheet(
            f"QListWidget {{ background: {C_FIELD}; border: 1px solid {C_BORDER};"
            f" border-radius: {R_BTN}px; color: {C_TEXT}; outline: none; }}"
            f"QListWidget::item {{ padding: 4px 9px; }}"
            f"QListWidget::item:selected {{ background: {C_BLUE}; color: #fff; border-radius: 4px; }}"
            f"QListWidget::item:hover:!selected {{ background: rgba(255,255,255,18); }}"
        )
        self.lay.addWidget(self.lst)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addStretch()
        cancel = _pill("İptal")
        ok = _pill("Ekle", primary=True)
        bar.addWidget(cancel)
        bar.addWidget(ok)
        self.lay.addLayout(bar)

        self.inp.textChanged.connect(self._filter)
        self.inp.returnPressed.connect(self._ok)
        self.lst.itemDoubleClicked.connect(self._ok)
        self.lst.itemClicked.connect(lambda item: self.inp.setText(item.text()))
        ok.clicked.connect(self._ok)
        cancel.clicked.connect(self.reject)

        self._filter("")
        self._place(260, 290)
        self.inp.setFocus()

    def _filter(self, text):
        q = text.strip().upper()
        items = [s for s in _BIST_SYMBOLS
                 if s not in self._existing and (not q or s.startswith(q))]
        self.lst.clear()
        self.lst.addItems(items)
        if self.lst.count() > 0:
            self.lst.setCurrentRow(0)

    def _ok(self):
        selected = self.lst.currentItem()
        typed = self.inp.text().strip().upper()
        candidate = selected.text() if selected else typed
        if candidate and sym_universe.is_known(candidate):
            self.value = candidate
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            row = self.lst.currentRow()
            if row < self.lst.count() - 1:
                self.lst.setCurrentRow(row + 1)
        elif event.key() == Qt.Key_Up:
            row = self.lst.currentRow()
            if row > 0:
                self.lst.setCurrentRow(row - 1)
        else:
            super().keyPressEvent(event)


class TargetSheet(_SheetDialog):
    """Giriş + çıkış hedefi tek sheet'te (result: ('save', e, x) | ('clear',) | None)."""

    def __init__(self, symbol, entry=None, exit_price=None, parent=None):
        super().__init__(parent)
        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        sym = QLabel(symbol)
        sym.setFont(_f(13, QFont.DemiBold))
        sym.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        sub = QLabel("giriş / çıkış hedefi")
        sub.setFont(_f(12))
        sub.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        h.addWidget(sym)
        h.addWidget(sub)
        h.addStretch()
        self.lay.addWidget(head)

        fields = QHBoxLayout()
        fields.setSpacing(10)
        w1, self.inp_entry = self._field("Giriş", _tr(entry) if entry is not None else "")
        w2, self.inp_exit  = self._field("Çıkış", _tr(exit_price) if exit_price is not None else "")
        self.inp_entry.setPlaceholderText("62,30")
        self.inp_exit.setPlaceholderText("71,00")
        fields.addWidget(w1)
        fields.addWidget(w2)
        self.lay.addLayout(fields)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        clear = _pill("Temizle")
        clear.setStyleSheet(
            f"QPushButton {{ background: rgba(255,69,58,42); color: {C_RED}; border: none;"
            f" border-radius: {R_BTN}px; padding: 0 11px; }}"
            "QPushButton:hover { background: rgba(255,69,58,70); }"
        )
        cancel = _pill("İptal")
        ok = _pill("Kaydet", primary=True)
        bar.addWidget(clear)
        bar.addStretch()
        bar.addWidget(cancel)
        bar.addWidget(ok)
        self.lay.addLayout(bar)

        self.result_value = None
        ok.clicked.connect(self._save)
        self.inp_entry.returnPressed.connect(self._save)
        self.inp_exit.returnPressed.connect(self._save)
        cancel.clicked.connect(self.reject)
        clear.clicked.connect(self._clear)
        self.inp_entry.setFocus()
        self._place(292, 150)

    # Boş girdi ile geçersiz girdiyi AYIRT etmek için sentinel: boş alan hedefi
    # bilinçli olarak temizler (None, geçerli); '71x' gibi çözümlenemeyen girdi
    # ise _INVALID döner ve _save accept'i engeller (sessizce None kaydetmez).
    _INVALID = object()

    def _num(self, text):
        text = text.strip()
        if not text:
            return None
        try:
            return _parse_price(text)
        except ValueError:
            return self._INVALID

    def _mark_invalid(self, inp, bad):
        # Geçersiz alanı kırmızı kenarlıkla işaretle; kullanıcı düzeltince temizlenir.
        border = C_RED if bad else C_BORDER
        inp.setStyleSheet(
            f"QLineEdit {{ background: {C_FIELD}; border: 1px solid {border};"
            f" border-radius: {R_BTN}px; color: {C_TEXT}; padding: 0 9px; }}"
            f"QLineEdit:focus {{ border-color: {C_RED if bad else C_BLUE}; }}"
        )

    def _save(self):
        entry = self._num(self.inp_entry.text())
        exit_ = self._num(self.inp_exit.text())
        bad_entry = entry is self._INVALID
        bad_exit = exit_ is self._INVALID
        self._mark_invalid(self.inp_entry, bad_entry)
        self._mark_invalid(self.inp_exit, bad_exit)
        if bad_entry or bad_exit:
            # Geçersiz sayı: accept ETME — kullanıcı hedef koyduğunu sanıp None'a
            # düşmesin. Odağı ilk hatalı alana ver.
            (self.inp_entry if bad_entry else self.inp_exit).setFocus()
            return
        self.result_value = ("save", entry, exit_)
        self.accept()

    def _clear(self):
        self.result_value = ("clear",)
        self.accept()


# ── Satırlar ────────────────────────────────────────────────────────────────
class Sparkline(QWidget):
    """Pseudo Heikin-Ashi sparkline — biriktirilen close fiyatlarından.
    HA_open[i] = (HA_open[i-1] + HA_close[i-1]) / 2
    HA_close[i] = close[i]   (sadece close ile yaklaşım)
    Yeşil mum: HA_close >= HA_open, Kırmızı: HA_close < HA_open
    """

    MAX = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setMinimumWidth(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._points = []

    def restore(self, points):
        self._points = list(points)[-self.MAX:]
        self.update()

    def push(self, price):
        # None VE NaN savunması: TV/BIST yolundan NaN fiyat sızabilir (data_fetcher
        # yfinance yolunda math.isnan filtreler ama TV yolunda değil); NaN nokta
        # paintEvent'te int(vy(nan)) → ValueError ile çizimi çökertir.
        if price is None or (isinstance(price, float) and math.isnan(price)):
            return
        self._points.append(price)
        if len(self._points) > self.MAX:
            self._points = self._points[-self.MAX:]
        self.update()

    @staticmethod
    def _ha_candles(closes):
        """Pseudo-HA: open ve close hesapla."""
        candles = []
        ha_open = closes[0]
        for c in closes:
            ha_close = c
            candles.append((ha_open, ha_close))
            ha_open = (ha_open + ha_close) / 2
        return candles

    def paintEvent(self, _):
        pts = self._points
        n = len(pts)
        if n < 2:
            return
        w, h = self.width(), self.height()
        if w < 4 or h < 2:
            return

        candles = self._ha_candles(pts)
        all_vals = [v for o, c in candles for v in (o, c)]
        lo, hi = min(all_vals), max(all_vals)
        span = (hi - lo) or 1.0

        GAP = 1
        cw = max(2, (w - GAP * (n - 1)) // n)   # mum genişliği

        def vy(v):
            return PAD + (1.0 - (v - lo) / span) * (h - 2 * PAD)

        PAD = 1.0
        p = QPainter(self)
        p.setPen(Qt.NoPen)

        for i, (ha_open, ha_close) in enumerate(candles):
            x = int(i * (cw + GAP))
            bull = ha_close >= ha_open
            color = QColor(C_GREEN if bull else C_RED)
            y_top = int(vy(max(ha_open, ha_close)))
            y_bot = int(vy(min(ha_open, ha_close)))
            body_h = max(1, y_bot - y_top)
            p.setBrush(color)
            p.drawRect(x, y_top, cw, body_h)

        p.end()





class StockRow(QWidget):
    remove_requested = Signal(str)
    levels_changed   = Signal(str, object, object)

    def __init__(self, symbol, entry=None, exit_price=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self._entry, self._exit, self._price = entry, exit_price, None
        self._press_pos = None
        self._reached = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("row")
        self.setFixedHeight(26)
        self.setCursor(Qt.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget()
        top.setFixedHeight(26)
        top.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(top)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        head = QWidget()
        head.setFixedWidth(60)
        head.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        self.lbl_symbol = QLabel(symbol)
        self.lbl_symbol.setFont(_f(11, QFont.DemiBold))
        self.lbl_symbol.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        self.dot = QLabel()
        self.dot.setFixedSize(5, 5)
        self.dot.setVisible(False)
        hl.addWidget(self.lbl_symbol)
        hl.addWidget(self.dot)
        hl.addStretch()

        self.spark = Sparkline()

        self.lbl_price = QLabel("—")
        self.lbl_price.setFont(_f(11))
        self.lbl_price.setFixedWidth(70)
        self.lbl_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_price.setStyleSheet(f"color: {C_TEXT2}; background: transparent;")

        self.lbl_pct = QLabel("—")
        self.lbl_pct.setFont(_f(11, QFont.DemiBold))
        self.lbl_pct.setFixedWidth(46)
        self.lbl_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_pct.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")

        lay.addWidget(head)
        lay.addWidget(self.spark, 1)
        lay.addWidget(self.lbl_price)
        lay.addWidget(self.lbl_pct)

        self.lbl_rsi = QLabel("")
        self.lbl_rsi.setFont(_f(8))
        self.lbl_rsi.setFixedWidth(80)
        self.lbl_rsi.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_rsi.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        self.lbl_rsi.setVisible(False)
        lay.addWidget(self.lbl_rsi)

        outer.addWidget(top)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._sync_target()

    def update_rsi(self, rsi: dict):
        parts = []
        for iv in (5, 15, 30, 60):
            v = rsi.get(iv)
            # NaN savunması: _calc_rsi NaN filtreler ama dış kaynaktan NaN
            # sızabilir; int(round(nan)) ValueError vermesin diye ele.
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                parts.append(f"{iv}m:{int(round(v))}")
        if not parts:
            self.lbl_rsi.setVisible(False)
            return
        # En kısa interval rengi temsil eder
        anchor = next(
            (rsi.get(iv) for iv in (5, 15, 30, 60)
             if rsi.get(iv) is not None
             and not (isinstance(rsi.get(iv), float) and math.isnan(rsi.get(iv)))),
            None,
        )
        if anchor is None:
            color = C_TEXT3
        elif anchor >= 70:
            color = C_GREEN
        elif anchor <= 30:
            color = C_RED
        else:
            color = C_TEXT3
        self.lbl_rsi.setStyleSheet(f"color: {color}; background: transparent;")
        self.lbl_rsi.setText("  ".join(parts))
        self.lbl_rsi.setVisible(True)

    # görünüm ------------------------------------------------------------
    def _paint_bg(self):
        tint = C_TINT_TGT if self._reached else "transparent"
        self.setStyleSheet(
            f"#row {{ background: {tint}; }}"
            f"#row:hover {{ background: {C_ROW_HOVER}; }}"
        )

    def _sync_target(self):
        has = self._entry is not None and self._exit is not None
        self.dot.setVisible(has)
        self._reached = False
        if has:
            # Yön farkındalığı: çıkış hedefi girişin ÜSTündeyse (long) fiyat
            # hedefe ≥ ile, ALTındaysa (short) ≤ ile ulaşır. Eski 'price >=
            # max(entry,exit)' yalnızca long'u düşünüyordu; short hedefte hiç
            # tetiklenmez, girişin üstünde yanlışlıkla 'ulaşıldı' yanardı.
            if self._price is not None:
                if self._exit >= self._entry:
                    self._reached = self._price >= self._exit
                else:
                    self._reached = self._price <= self._exit
            self.dot.setStyleSheet(
                f"background: {C_YELLOW if self._reached else C_GREEN}; border-radius: 2px;"
            )
            tip = f"Giriş {_tr(self._entry)}  ·  Çıkış {_tr(self._exit)}"
            if self._price is not None and self._entry is not None and self._entry != 0:
                pnl = (self._price - self._entry) / self._entry * 100
                sign = "+" if pnl >= 0 else "−"
                tip += f"  ·  {sign}{_tr(abs(pnl), 1)}%"
            self.setToolTip(tip)
        else:
            self.setToolTip("")
        self._paint_bg()

    def update_data(self, price, change_pct):
        self._price = price
        self.lbl_price.setText("—" if price is None else _tr(price))
        if change_pct is None:
            self.lbl_pct.setText("—")
            self.lbl_pct.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        else:
            up = change_pct >= 0
            self.lbl_pct.setText(("+" if up else "−") + _tr(abs(change_pct)))
            self.lbl_pct.setStyleSheet(
                f"color: {C_GREEN if up else C_RED}; background: transparent;"
            )
        # Sparkline'ı change_pct'ten BAĞIMSIZ, fiyat geldiğinde güncelle: TV
        # paketinde chp None gelip price dolu olabilir ({price, change_pct:None});
        # push'u yüzde dalına bağlamak bu sembolde grafiği kalıcı boş bırakırdı.
        # push zaten None/NaN-guard'lı.
        self.spark.push(price)
        self._sync_target()

    # sürükle-bırak ------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._press_pos is None:
            return
        if (e.position().toPoint() - self._press_pos).manhattanLength() < 8:
            return
        self._press_pos = None
        pm = self.grab()
        ghost = QPixmap(pm.size())
        ghost.fill(Qt.transparent)
        p = QPainter(ghost)
        p.setOpacity(0.85)
        p.drawPixmap(0, 0, pm)
        p.end()
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_ROW, self.symbol.encode())
        drag.setMimeData(mime)
        drag.setPixmap(ghost)
        drag.setHotSpot(QPoint(24, self.height() // 2))
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, e):
        if self._press_pos is not None and e.button() == Qt.LeftButton:
            self._press_pos = None
            self._open_target()

    # menü ---------------------------------------------------------------
    def _ctx_menu(self, pos):
        m = _menu(self)
        m.addAction("Hedef belirle…", self._open_target)
        m.addAction("Hedefi temizle", self._clear_target)
        m.addSeparator()
        m.addAction("Listeden kaldır", lambda: self.remove_requested.emit(self.symbol))
        m.exec(self.mapToGlobal(pos))

    def _open_target(self):
        dlg = TargetSheet(self.symbol, self._entry, self._exit, parent=self.window())
        dlg.exec()
        res = dlg.result_value
        if not res:
            return
        if res[0] == "clear":
            self._entry = self._exit = None
        else:
            self._entry, self._exit = res[1], res[2]
        self._sync_target()
        self.levels_changed.emit(self.symbol, self._entry, self._exit)

    def _clear_target(self):
        self._entry = self._exit = None
        self._sync_target()
        self.levels_changed.emit(self.symbol, None, None)


class GroupHeader(QWidget):
    remove_requested = Signal(str)
    rename_requested = Signal(str)
    move_requested   = Signal(str, int)
    collapse_toggled = Signal(str, bool)

    def __init__(self, uid, count=0, collapsed=False, parent=None):
        super().__init__(parent)
        self.symbol = uid
        self._collapsed = collapsed
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(16)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(5)

        name, _ = _parse_sep_symbol(uid)
        self.lbl = QLabel((name or "Takip").upper())
        self.lbl.setFont(_f(9, QFont.Bold))
        self.lbl.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")

        self.chev = QLabel("›" if collapsed else "⌄")
        self.chev.setFont(_f(9))
        self.chev.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")

        self.cnt = QLabel(str(count))
        self.cnt.setFont(_f(9))
        self.cnt.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")

        lay.addWidget(self.lbl)
        lay.addWidget(self.chev)
        lay.addStretch()
        lay.addWidget(self.cnt)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

    def set_count(self, n):
        self.cnt.setText(str(n))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._collapsed = not self._collapsed
            self.chev.setText("›" if self._collapsed else "⌄")
            self.collapse_toggled.emit(self.symbol, self._collapsed)

    def _ctx_menu(self, pos):
        m = _menu(self)
        m.addAction("Yeniden adlandır…", lambda: self.rename_requested.emit(self.symbol))
        m.addAction("Yukarı taşı", lambda: self.move_requested.emit(self.symbol, -1))
        m.addAction("Aşağı taşı", lambda: self.move_requested.emit(self.symbol, +1))
        m.addSeparator()
        m.addAction("Bölümü kaldır", lambda: self.remove_requested.emit(self.symbol))
        m.exec(self.mapToGlobal(pos))


class RowsHost(QWidget):
    """Sürükle-bırak sıralamayı kabul eden liste gövdesi."""
    dropped = Signal(str, object, bool)   # taşınan sembol, hedef sembol (None=sona), hedef_başlık_mı

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background: transparent;")
        self._order = []            # [(symbol, widget)]
        self.indicator = QFrame(self)
        self.indicator.setFixedHeight(2)
        self.indicator.setStyleSheet(f"background: {C_BLUE}; border-radius: 1px;")
        self.indicator.hide()

    def set_order(self, order):
        self._order = order

    def _target_at(self, y):
        """y konumundaki bırakma hedefini bul.

        Döndürür: (sym, top_y, is_header). Görünür widget'lar arasında dikey
        ortası y'nin altında kalan İLK widget hedeftir. is_header True ise
        hedef bir bölüm başlığıdır (uid `---` ile başlar). Liste sonu →
        (None, None, False).
        """
        for sym, w in self._order:
            if not w.isVisible():
                continue
            top_left = w.mapTo(self, QPoint(0, 0))
            if y < top_left.y() + w.height() / 2:
                return sym, top_left.y(), sym.startswith(_SEP_SYMBOL)
        return None, None, False

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME_ROW):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasFormat(MIME_ROW):
            return
        y = int(e.position().y())
        sym, top, is_header = self._target_at(y)
        if top is None:
            top = self.height() - 2
        elif is_header:
            # başlığa bırakınca çizgiyi başlığın ALT kenarına al → "bölüme giriyor"
            w = next((w for s, w in self._order if s == sym), None)
            if w is not None:
                top = w.mapTo(self, QPoint(0, 0)).y() + w.height()
        self.indicator.setGeometry(10, max(0, top - 1), self.width() - 20, 2)
        self.indicator.raise_()
        self.indicator.show()
        e.acceptProposedAction()

    def dragLeaveEvent(self, _):
        self.indicator.hide()

    def dropEvent(self, e):
        self.indicator.hide()
        if not e.mimeData().hasFormat(MIME_ROW):
            return
        moved = bytes(e.mimeData().data(MIME_ROW)).decode()
        target, _unused, is_header = self._target_at(int(e.position().y()))
        e.acceptProposedAction()
        self.dropped.emit(moved, target, is_header)


# ── Ana pencere ─────────────────────────────────────────────────────────────
class OverlayWindow(QWidget):
    # Poll worker (arka plan thread) yeni tweet id'lerini bu sinyalle
    # ana thread'e iletir; UI/state değişikliği yalnızca ana thread'de olur.
    tw_poll_result = Signal(set)
    # Poll HATASI (arka plan thread) → ana thread'de status/backoff. Eskiden poll
    # hatası (rate-limit/500/ağ) sessizce yutuluyordu; kullanıcı arızayı görmezdi.
    tw_poll_error = Signal(str)
    # İlk yükleme (arka plan thread) sonucu: (tweets, users, hata_metni)
    tw_load_result = Signal(object)
    # RSI worker BİTTİ sinyali → _rsi_fetching bayrağını ANA thread'de kapat.
    # (Diğer re-entrancy bayrakları _fetching/_tw_loading/_notes_loading ana
    # thread'de kapanıyor; eskiden bu bayrak worker'ın finally'sinde cross-thread
    # yazılıyordu — projenin kendi thread-safety kuralını kıran tek istisnaydı.)
    rsi_done = Signal()

    def __init__(self, signals):
        super().__init__()
        self._signals = signals
        self._mode = 0
        self._fetching = False
        self.stocks = load_stocks()
        self.rows = {}
        self.headers = {}
        self.cards = {}   # {uid: card widget} — collapse için
        self._sections = []   # [(uid, section, card, [(sym,row)])] — arama görünürlüğü
        self._spark_history = {}   # {symbol: points} — rebuild'ler arası korunur
        self._rsi_cache = {}       # {symbol: {5:x,15:x,30:x,60:x}} — rebuild'ler arası korunur
        self._collapsed_sections = {}
        self._filter = ""

        self._tw_seen = set()        # görülmüş tüm tweet id'leri
        self._tw_unread = set()      # sekme rozetindeki sayaç
        self._tw_hl = set()          # satırlarda mavi vurgulananlar
        self._tw_filter = None       # aktif sembol çipi
        self._tw_tweets = []
        self._tw_users = {}
        self._tw_last = "—"
        self._tw_rows = None         # [(sym, row_widget)] — _twitter_render kurar
        self._tw_chip_widgets = []   # [(sym_or_None, chip_widget)]
        self._tw_symbols = load_tw_symbols()   # izlenen semboller (kalıcı)

        self._pinned = False
        # Varsayılan floating KAPALI: açıkken aynı sekmeye tekrar tıklama ve
        # dışarı-tıkla-kapat devre dışı kalır, yeni kullanıcı paneli kapatamaz.
        # Kullanıcı ⬆ butonuyla bilinçli açabilir.
        self._floating = False
        self._pin_btns = []
        self._float_btns = []
        self._monitor_btns = []
        self._drag_pos = None  # sürükleme için

        self._notes = []
        self._current_note = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._notes_save_now)

        # Arama debounce — her tuşta değil, yazma durunca rebuild
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        QApplication.instance().installEventFilter(self)

        self._build_ui()

        self._current_sc = _main_screen()
        sc_avail = QApplication.primaryScreen().availableGeometry()
        win_h = sc_avail.height() // 2
        win_y = sc_avail.y() + sc_avail.height() - win_h
        self._anim = QPropertyAnimation(self.panel, b"maximumWidth")
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._anim.valueChanged.connect(lambda w: (
            self.setFixedWidth(TAB_W + w),
            self.move(self._current_sc.x() + self._current_sc.width() - TAB_W - w, self.y())
        ))
        self.panel.setMaximumWidth(0)
        self.setFixedSize(TAB_W, win_h)
        self.move(self._current_sc.x() + self._current_sc.width() - TAB_W, win_y)

        self.stock_timer = QTimer(self)
        self.stock_timer.timeout.connect(self._stocks_refresh)
        self.stock_timer.start(REFRESH_INTERVAL_MS)
        if self.stocks:
            self._stocks_refresh()
        # Notlar sekmeye ilk geçişte yüklenir (_toggle içinde); başlangıçta gereksiz istek yok.
        QTimer.singleShot(500, self._install_global_mouse_monitor)
        self._outside_click_timer = QTimer(self)
        self._outside_click_timer.timeout.connect(self._check_outside_click)
        self._outside_click_timer.start(150)

        self._twitter_poll_timer = QTimer(self)
        self._twitter_poll_timer.timeout.connect(self._twitter_poll)
        self._twitter_poll_timer.start(60_000)
        self.tw_poll_result.connect(self._twitter_poll_apply)
        self.tw_poll_error.connect(self._twitter_poll_error)
        self.tw_load_result.connect(self._twitter_load_apply)
        self.rsi_done.connect(self._on_rsi_done)

        self._rsi_timer = QTimer(self)
        self._rsi_timer.timeout.connect(self._rsi_refresh)
        self._rsi_timer.start(300_000)  # 5 dakikada bir
        QTimer.singleShot(3000, self._rsi_refresh)  # ilk yüklemede 3sn sonra başlat

    # ── UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tab_col = QWidget()
        tab_col.setFixedWidth(TAB_W)
        tc = QVBoxLayout(tab_col)
        tc.setContentsMargins(0, 0, 0, 0)
        tc.setSpacing(TAB_GAP)

        self.tab_stock = self._make_tab("◧", 1)
        self.tab_notes = self._make_tab("✎", 2)
        self.tab_twitter = self._make_tab("𝕏", 3)
        tc.addStretch()
        tc.addWidget(self.tab_stock)
        tc.addWidget(self.tab_notes)
        tc.addWidget(self.tab_twitter)

        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(
            f"#panel {{ background: {C_PANEL_BG};"
            f" border-top-left-radius: {R_PANEL}px;"
            f" border-bottom-left-radius: {R_PANEL}px;"
            f" border: 1px solid {C_BORDER}; border-right: none; }}"
        )
        self.panel.setMinimumWidth(0)
        self.panel.setMaximumWidth(PANEL_W)

        pnl = QVBoxLayout(self.panel)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        self.stocks_page = self._build_stocks_page()
        pnl.addWidget(self.stocks_page)
        self.notes_page = self._build_notes_page()
        self.notes_page.setVisible(False)
        pnl.addWidget(self.notes_page)
        self.twitter_page = self._build_twitter_page()
        self.twitter_page.setVisible(False)
        pnl.addWidget(self.twitter_page)

        root.addWidget(self.panel)
        root.addWidget(tab_col)

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._update_pin_style()

    def _update_pin_style(self):
        on  = f"background: rgba(48,209,88,40); border-radius: 8px; color: {C_GREEN};"
        off = "background: transparent; color: rgba(235,235,245,100);"
        for btn in self._pin_btns:
            btn.setStyleSheet(on if self._pinned else off)

    def _toggle_float(self):
        self._floating = not self._floating
        self._apply_float()
        self._update_float_style()

    def _apply_float(self):
        flags = self.windowFlags()
        if self._floating:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        if self._floating:
            _set_ns_window_level(self, level=1001, collection_behavior=_COLLECTION_BEHAVIOR)
        else:
            _set_ns_window_level(self, level=0, collection_behavior=0)

    def _update_float_style(self):
        on  = f"background: rgba(10,132,255,40); border-radius: 8px; color: {C_BLUE};"
        off = "background: transparent; color: rgba(235,235,245,100);"
        for btn in self._float_btns:
            btn.setStyleSheet(on if self._floating else off)

    def _cycle_monitor(self):
        screens = QApplication.screens()
        if len(screens) < 2:
            return
        cur = self.screen()
        try:
            idx = screens.index(cur)
        except ValueError:
            idx = 0
        self._reposition_to_screen(screens[(idx + 1) % len(screens)])

    def _reposition_to_screen(self, screen):
        sc = screen.geometry()
        sc_avail = screen.availableGeometry()
        win_h = sc_avail.height() // 2
        win_y = sc_avail.y() + sc_avail.height() - win_h
        self._current_sc = sc
        # Panel AÇIKKEN (floating modda ⊞ ile monitör değiştirmek yalnızca panel
        # açıkken mümkün) pencereyi TAB_W'ye daraltmak paneli görünmez bırakır ve
        # animasyon durumu (panel.maximumWidth) pencere genişliğiyle desenkronize
        # olur. Panelin mevcut açık genişliğini (maximumWidth) koruyarak senkronu
        # sürdür.
        panel_w = self.panel.maximumWidth() if self._mode != 0 else 0
        win_w = TAB_W + panel_w
        self.setFixedSize(win_w, win_h)
        self.move(sc.x() + sc.width() - win_w, win_y)
        if self._floating:
            _set_ns_window_level(self, level=1001, collection_behavior=_COLLECTION_BEHAVIOR)

    def _make_tab(self, glyph, mode):
        tab = QWidget()
        tab.setFixedSize(TAB_W, TAB_H)
        tab.setCursor(Qt.PointingHandCursor)
        tab.setObjectName(f"tab{mode}")
        lyt = QVBoxLayout(tab)
        lyt.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(glyph)
        lbl.setFont(_f(14))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: transparent;")
        lyt.addWidget(lbl)
        tab._label = lbl
        tab._mode = mode
        if mode == 3:
            self.tab_badge = QLabel("", tab)
            self.tab_badge.setFont(_f(9, QFont.Bold))
            self.tab_badge.setAlignment(Qt.AlignCenter)
            self.tab_badge.setFixedSize(16, 14)
            self.tab_badge.move(TAB_W - 20, 6)
            self.tab_badge.setStyleSheet(
                f"background: {C_RED}; color: #ffffff; border-radius: 7px;"
            )
            self.tab_badge.hide()
        tab.mousePressEvent = lambda e, m=mode: (
            self._quit_menu(e) if e.button() == Qt.RightButton else self._toggle(m)
        )
        self._paint_tab(tab, False)
        return tab

    def _paint_tab(self, tab, active, alert=False):
        bg = C_BLUE if active else "rgba(48, 48, 50, 214)"
        border = "none" if active else f"1px solid {C_BORDER}"
        tab.setStyleSheet(
            f"#{tab.objectName()} {{ background: {bg}; border: {border}; border-right: none;"
            f" border-top-left-radius: {R_TAB}px; border-bottom-left-radius: {R_TAB}px; }}"
        )
        tab._label.setStyleSheet(
            f"color: {'#ffffff' if active else C_TEXT2}; background: transparent;"
        )

    def _update_tab_badge(self):
        n = len(self._tw_unread)
        if not hasattr(self, "tab_badge"):
            return
        if n and self._mode != 3:
            self.tab_badge.setText(str(n) if n < 100 else "99")
            self.tab_badge.show()
            self.tab_badge.raise_()
        else:
            self.tab_badge.hide()

    def _control_button(self, glyph, tooltip, handler, registry, monitor=False):
        """Başlık kontrol butonu (pin/float/monitor) üret — tek yerden.

        _head_row ve _build_twitter_page aynı pin/float/monitor bloklarını
        kopyalamak yerine bunu çağırır (DRY; bir davranış değişince tek yer).
        """
        b = QLabel(glyph)
        b.setFixedSize(18, 18)
        b.setAlignment(Qt.AlignCenter)
        b.setFont(_f(11))
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tooltip)
        b.mousePressEvent = lambda e: handler()
        if monitor:
            b.setVisible(len(QApplication.screens()) > 1)
        registry.append(b)
        return b

    def _head_row(self, title, status_text=""):
        """Kompakt sayfa başlığı: 12 px başlık + raptiye + sağda durum, altında saç çizgisi."""
        w = QWidget()
        w.setObjectName("headrow")
        w.setStyleSheet(f"#headrow {{ border-bottom: 1px solid {C_HAIRLINE}; }}")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 8, 12, 7)
        h.setSpacing(7)
        lbl = QLabel(title)
        lbl.setFont(_f(12, QFont.DemiBold))
        lbl.setStyleSheet(f"color: {C_TEXT}; background: transparent;")

        pin_btn = self._control_button(
            "📌", "Sürekli açık tut", self._toggle_pin, self._pin_btns)
        float_btn = self._control_button(
            "⬆", "Her zaman üstte / floating", self._toggle_float, self._float_btns)
        monitor_btn = self._control_button(
            "⊞", "Diğer monitöre taşı", self._cycle_monitor, self._monitor_btns,
            monitor=True)

        status = QLabel(status_text)
        status.setFont(_f(10))
        status.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(pin_btn)
        h.addWidget(float_btn)
        h.addWidget(monitor_btn)
        h.addWidget(status)

        # Başlık satırından sürükleyerek pencereyi taşı
        def _head_mouse_press(e):
            if e.button() == Qt.LeftButton:
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        def _head_mouse_move(e):
            if e.buttons() == Qt.LeftButton and self._drag_pos is not None:
                self.move(e.globalPosition().toPoint() - self._drag_pos)
                self._current_sc = self.screen().geometry()
        def _head_mouse_release(e):
            self._drag_pos = None
        w.mousePressEvent = _head_mouse_press
        w.mouseMoveEvent = _head_mouse_move
        w.mouseReleaseEvent = _head_mouse_release
        w.setCursor(Qt.SizeAllCursor)

        # ilk oluşturmada stil uygula
        self._update_pin_style()
        self._update_float_style()
        return w, status

    def _foot_row(self):
        w = QWidget()
        w.setObjectName("footrow")
        w.setStyleSheet(f"#footrow {{ border-top: 1px solid {C_HAIRLINE}; }}")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 6, 12, 7)
        h.setSpacing(10)
        return w, h

    def _scroll_area(self, host):
        sc = QScrollArea()
        sc.setWidget(host)
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sc.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,40);"
            " border-radius: 2px; min-height: 24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        return sc

    # ── Hisse sayfası ───────────────────────────────────────────────────
    def _build_stocks_page(self):
        page = QWidget()
        pnl = QVBoxLayout(page)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        head, self.lbl_stock_status = self._head_row("Portföy")
        pnl.addWidget(head)

        # ince arama satırı
        search_wrap = QWidget()
        search_wrap.setObjectName("searchrow")
        search_wrap.setStyleSheet(f"#searchrow {{ border-bottom: 1px solid {C_HAIRLINE}; }}")
        sw = QHBoxLayout(search_wrap)
        sw.setContentsMargins(12, 5, 12, 6)
        sw.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara")
        self.search.setFont(_f(11))
        self.search.setFixedHeight(20)
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {C_FIELD}; border: none; border-radius: 5px;"
            f" color: {C_TEXT}; padding: 0 7px; }}"
        )
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._add_from_search)
        self.btn_add_inline = QPushButton("Ekle")
        self.btn_add_inline.setFont(_f(10, QFont.DemiBold))
        self.btn_add_inline.setFixedHeight(18)
        self.btn_add_inline.setCursor(Qt.PointingHandCursor)
        self.btn_add_inline.setStyleSheet(
            f"QPushButton {{ background: {C_BLUE}; color: #fff; border: none;"
            f" border-radius: 5px; padding: 0 8px; }}"
            f"QPushButton:hover {{ background: {C_BLUE_HOVER}; }}"
        )
        self.btn_add_inline.clicked.connect(self._add_from_search)
        self.btn_add_inline.setVisible(False)
        sw.addWidget(self.search)
        sw.addWidget(self.btn_add_inline)
        pnl.addWidget(search_wrap)

        self.host = RowsHost()
        self.rows_layout = QVBoxLayout(self.host)
        self.rows_layout.setContentsMargins(0, 4, 0, 6)
        self.rows_layout.setSpacing(6)
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.host.dropped.connect(self._on_dropped)
        pnl.addWidget(self._scroll_area(self.host), 1)

        self.lbl_empty = QLabel("Takip listen boş\nSembolü yaz, listeden ekle.")
        self.lbl_empty.setFont(_f(11))
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        self.rows_layout.addWidget(self.lbl_empty)

        bar, bl = self._foot_row()
        b_add = _flat("+ Hisse")
        b_add.clicked.connect(self._add_stock)
        b_sec = _flat("+ Bölüm")
        b_sec.clicked.connect(self._add_separator)
        b_ref = _flat("↻")
        b_ref.clicked.connect(self._stocks_refresh)
        bl.addWidget(b_add)
        bl.addWidget(b_sec)
        bl.addStretch()
        bl.addWidget(b_ref)
        pnl.addWidget(bar)

        self._rebuild_rows()
        return page

    # ── Notlar sayfası ──────────────────────────────────────────────────
    def _build_notes_page(self):
        page = QWidget()
        pnl = QVBoxLayout(page)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        head, self.lbl_notes_status = self._head_row("Notlar")
        pnl.addWidget(head)

        self.notes_list = QListWidget()
        self.notes_list.setFixedHeight(116)
        self.notes_list.setFont(_f(11))
        self.notes_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none;"
            f" border-bottom: 1px solid {C_HAIRLINE};"
            f" color: {C_TEXT2}; padding: 0; outline: none; }}"
            f"QListWidget::item {{ padding: 5px 12px; }}"
            f"QListWidget::item:hover {{ background: {C_ROW_HOVER}; }}"
            f"QListWidget::item:selected {{ background: rgba(10,132,255,36); color: #ffffff; }}"
        )
        self.notes_list.currentRowChanged.connect(self._note_selected)
        self.notes_list.itemDoubleClicked.connect(self._rename_note)
        pnl.addWidget(self.notes_list)

        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Not içeriği…")
        self.notes_editor.setEnabled(False)
        self.notes_editor.setFont(_f(11))
        self.notes_editor.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none;"
            f" color: {C_TEXT2}; padding: 10px 12px; }}"
            "QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,40);"
            " border-radius: 2px; min-height: 24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self.notes_editor.textChanged.connect(self._note_text_changed)
        pnl.addWidget(self.notes_editor, 1)

        bar, bl = self._foot_row()
        hint = QLabel("otomatik kayıt · 1,5 sn")
        hint.setFont(_f(10))
        hint.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")
        b_new = _flat("+ Not")
        b_new.clicked.connect(self._add_note)
        b_ref = _flat("↻")
        b_ref.clicked.connect(self._notes_load)
        b_del = _flat("Sil", color=C_RED)
        b_del.clicked.connect(self._delete_note)
        bl.addWidget(hint)
        bl.addStretch()
        bl.addWidget(b_new)
        bl.addWidget(b_ref)
        bl.addWidget(b_del)
        pnl.addWidget(bar)
        return page

    def _build_twitter_page(self):
        page = QWidget()
        pnl = QVBoxLayout(page)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        # başlık: 𝕏 + okunmamış rozeti + tümünü okundu işaretle
        head = QWidget()
        head.setObjectName("headrow")
        head.setStyleSheet(f"#headrow {{ border-bottom: 1px solid {C_HAIRLINE}; }}")
        h = QHBoxLayout(head)
        h.setContentsMargins(12, 8, 12, 7)
        h.setSpacing(7)
        title = QLabel("𝕏")
        title.setFont(_f(12, QFont.DemiBold))
        title.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        self.lbl_tw_count = QLabel("")
        self.lbl_tw_count.setFont(_f(9, QFont.Bold))
        self.lbl_tw_count.setStyleSheet(
            f"color: #ffffff; background: {C_RED}; border-radius: 4px; padding: 1px 5px;"
        )
        self.lbl_tw_count.setVisible(False)
        self.btn_tw_read = _flat("tümünü okundu işaretle")
        self.btn_tw_read.setFont(_f(10))
        self.btn_tw_read.clicked.connect(self._twitter_mark_read)
        self.btn_tw_read.setVisible(False)
        self.lbl_twitter_status = QLabel("")
        self.lbl_twitter_status.setFont(_f(10))
        self.lbl_twitter_status.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")

        # Pin/float/monitor kontrolleri — Portföy/Notlar başlıklarıyla tutarlı
        # olsun diye Twitter başlığına da eklenir (aksi halde bu sekmedeyken
        # kullanıcı pencereyi sabitleyemez/floating yapamaz/monitör değiştiremez).
        # _head_row ile aynı fabrikayı kullan (DRY).
        pin_btn = self._control_button(
            "📌", "Sürekli açık tut", self._toggle_pin, self._pin_btns)
        float_btn = self._control_button(
            "⬆", "Her zaman üstte / floating", self._toggle_float, self._float_btns)
        monitor_btn = self._control_button(
            "⊞", "Diğer monitöre taşı", self._cycle_monitor, self._monitor_btns,
            monitor=True)

        h.addWidget(title)
        h.addWidget(self.lbl_tw_count)
        h.addWidget(self.lbl_twitter_status)
        h.addStretch()
        h.addWidget(self.btn_tw_read)
        h.addWidget(pin_btn)
        h.addWidget(float_btn)
        h.addWidget(monitor_btn)
        pnl.addWidget(head)
        self._update_pin_style()
        self._update_float_style()

        # sembol çipleri
        self.tw_chips = QWidget()
        self.tw_chips.setObjectName("chiprow")
        self.tw_chips.setStyleSheet(f"#chiprow {{ border-bottom: 1px solid {C_HAIRLINE}; }}")
        self.tw_chips_layout = QHBoxLayout(self.tw_chips)
        self.tw_chips_layout.setContentsMargins(12, 6, 12, 7)
        self.tw_chips_layout.setSpacing(4)
        self.tw_chips_layout.setAlignment(Qt.AlignLeft)
        pnl.addWidget(self.tw_chips)

        # akış
        self.twitter_host = QWidget()
        self.twitter_host.setStyleSheet("background: transparent;")
        self.twitter_layout = QVBoxLayout(self.twitter_host)
        self.twitter_layout.setContentsMargins(0, 0, 0, 6)
        self.twitter_layout.setSpacing(0)
        self.twitter_layout.setAlignment(Qt.AlignTop)
        pnl.addWidget(self._scroll_area(self.twitter_host), 1)

        bar, bl = self._foot_row()
        self.lbl_tw_time = QLabel("son: —")
        self.lbl_tw_time.setFont(_f(10))
        self.lbl_tw_time.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")
        b_ref = _flat("↻ Yenile")
        b_ref.clicked.connect(self._twitter_load)
        b_add_sym = _flat("+ Sembol")
        b_add_sym.clicked.connect(self._twitter_add_symbol)
        bl.addWidget(self.lbl_tw_time)
        bl.addStretch()
        bl.addWidget(b_add_sym)
        bl.addWidget(b_ref)
        pnl.addWidget(bar)
        return page

    # ── 𝕏 yardımcıları ──────────────────────────────────────────────────
    def _twitter_query(self):
        # config.TWITTER_QUERY doluysa aynen kullan (opsiyonel override);
        # boşsa izlenen sembollerden üret.
        override = (config.TWITTER_QUERY or "").strip()
        if override:
            return override
        return twitter_query(self._tw_symbols)

    def _twitter_add_symbol(self):
        existing = list(self._tw_symbols)
        dlg = StockPickerSheet(existing=existing, parent=self)
        dlg.exec()
        sym = (dlg.value or "").upper()
        if sym and sym not in self._tw_symbols:
            self._tw_symbols.append(sym)
            save_tw_symbols(self._tw_symbols)
            self._twitter_load()

    def _twitter_remove_symbol(self, sym):
        if sym in self._tw_symbols:
            self._tw_symbols.remove(sym)
            if self._tw_filter == sym:
                self._tw_filter = None
            save_tw_symbols(self._tw_symbols)
            self._twitter_load()   # sorgu değişti; yeni akışı çek

    def _twitter_token(self):
        return config.TWITTER_BEARER_TOKEN

    def _twitter_mark_read(self):
        self._tw_hl.clear()
        self._tw_unread.clear()
        self._update_tab_badge()
        self._twitter_render()

    def _twitter_style_chip(self, w, active):
        """Çip aktiflik rengini uygula (widget yeniden kurmadan güncellenebilir)."""
        bg = C_BLUE if active else "rgba(255,255,255,18)"
        fg = "#ffffff" if active else C_TEXT3
        w.setStyleSheet(
            f"#chip {{ background: {bg}; border-radius: 5px; }}"
            f"#chip:hover {{ background: {C_BLUE if active else 'rgba(255,255,255,34)'}; }}"
        )
        lbl = getattr(w, "_chip_lbl", None)
        cnt = getattr(w, "_chip_cnt", None)
        if lbl is not None:
            lbl.setStyleSheet(f"color: {fg}; background: transparent;")
        if cnt is not None:
            cnt.setStyleSheet(f"color: {fg if active else C_TEXT4}; background: transparent;")

    def _twitter_chip(self, label, count, active, on_click, removable=False):
        w = QWidget()
        w.setCursor(Qt.PointingHandCursor)
        w.setObjectName("chip")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(7, 2, 7 if not removable else 3, 3)
        lay.setSpacing(4)
        lbl = QLabel(label)
        lbl.setFont(_f(10, QFont.DemiBold))
        cnt = QLabel(str(count))
        cnt.setFont(_f(10))
        w._chip_lbl = lbl        # _twitter_style_chip yeniden renklendirebilsin
        w._chip_cnt = cnt
        lay.addWidget(lbl)
        lay.addWidget(cnt)
        if removable:
            x_btn = QLabel("×")
            x_btn.setFont(_f(11))
            x_btn.setStyleSheet(f"color: {C_TEXT3}; background: transparent; padding: 0 2px;")
            x_btn.setCursor(Qt.PointingHandCursor)
            x_btn.mousePressEvent = lambda e, s=label: (e.accept(), self._twitter_remove_symbol(s))
            lay.addWidget(x_btn)
        w.mousePressEvent = lambda e, cb=on_click: cb()
        self._twitter_style_chip(w, active)
        return w

    def _twitter_row(self, tw, user, unread, symbol):
        row = QWidget()
        row.setObjectName("twrow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setCursor(Qt.PointingHandCursor)
        row.setStyleSheet(
            f"#twrow {{ background: {C_TINT_NEW if unread else 'transparent'};"
            f" border-bottom: 1px solid {C_HAIRLINE}; }}"
            f"#twrow:hover {{ background: {C_ROW_HOVER}; }}"
        )
        tweet_url = f"https://twitter.com/i/web/status/{tw.get('id', '')}"
        row.mousePressEvent = lambda e, u=tweet_url: subprocess.Popen(["open", u])

        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 7, 12, 8)
        lay.setSpacing(8)

        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(
            f"background: {C_BLUE if unread else 'transparent'}; border-radius: 3px;"
        )
        dot_wrap = QWidget()
        dot_wrap.setFixedWidth(6)
        dw = QVBoxLayout(dot_wrap)
        dw.setContentsMargins(0, 4, 0, 0)
        dw.setSpacing(0)
        dw.addWidget(dot)
        dw.addStretch()
        lay.addWidget(dot_wrap)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        uname = user.get("username") or user.get("name") or "—"
        lbl_user = QLabel("@" + uname)
        lbl_user.setTextFormat(Qt.PlainText)
        lbl_user.setFont(_f(11, QFont.DemiBold))
        lbl_user.setStyleSheet(
            f"color: {C_TEXT if unread else C_TEXT2}; background: transparent;"
        )
        top.addWidget(lbl_user)
        if symbol:
            chip = QLabel(symbol)
            chip.setFont(_f(9, QFont.DemiBold))
            chip.setStyleSheet(
                f"color: {C_TEXT2 if unread else C_TEXT4};"
                " background: rgba(255,255,255,20); border-radius: 3px; padding: 0 4px;"
            )
            top.addWidget(chip)
        top.addStretch()
        ts = tw.get("created_at", "")
        lbl_ts = QLabel(_tw_ago(ts))
        lbl_ts.setFont(_f(10))
        lbl_ts.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")
        top.addWidget(lbl_ts)
        body.addLayout(top)

        text = " ".join(tw.get("text", "").split())
        lbl_text = QLabel(text)
        lbl_text.setTextFormat(Qt.PlainText)
        lbl_text.setFont(_f(11))
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet(
            f"color: {C_TEXT2 if unread else C_TEXT3}; background: transparent;"
        )
        body.addWidget(lbl_text)
        lay.addLayout(body, 1)
        return row

    def _twitter_render(self):
        for i in reversed(range(self.twitter_layout.count())):
            w = self.twitter_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        for i in reversed(range(self.tw_chips_layout.count())):
            w = self.tw_chips_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        tweets = self._tw_tweets
        syms = self._tw_symbols

        # Tweet başına eşleşen TÜM sembolleri BİR KEZ hesapla; counts/filtre/
        # gösterim aynı sonucu kullansın (aksi halde regex 3× çalışırdı). Çok
        # sembollü tweet ('THYAO ve AKBNK') her ilgili sembolde sayılır/görünür.
        syms_by_id = {}

        def syms_of(tw):
            tid = tw.get("id", "")
            s = syms_by_id.get(tid)
            if s is None:
                s = symbols_of_tweet(tw.get("text", ""), syms)
                syms_by_id[tid] = s
            return s

        counts = {}
        matched_ids = set()
        for tw in tweets:
            ms = syms_of(tw)
            if ms:
                matched_ids.add(tw.get("id", ""))
            for s in ms:
                counts[s] = counts.get(s, 0) + 1

        # Çipleri sakla ki _twitter_set_filter widget yeniden kurmadan yalnızca
        # renk/görünürlük güncelleyebilsin. [(sym_or_None, chip_widget)]
        self._tw_chip_widgets = []
        all_chip = self._twitter_chip(
            "Tümü", len(tweets), self._tw_filter is None,
            lambda: self._twitter_set_filter(None))
        # 'Tümü' sembol çiplerinin toplamından farklı olabilir: bir tweet birden
        # çok sembole sayılabildiğinden toplam > len(tweets) olabilir; hiçbir
        # izlenen sembolü içermeyen tweet ise hiçbir sembol çipine düşmez. Çip
        # sayaç toplamı yerine 'kaç tweet en az bir sembol içeriyor'u kıyasla.
        matched = len(matched_ids)
        if matched < len(tweets):
            all_chip.setToolTip(
                f"{len(tweets)} tweet'in {matched} tanesi izlenen bir sembol "
                "içeriyor; kalanı yalnızca 'Tümü'de görünür.")
        self.tw_chips_layout.addWidget(all_chip)
        self._tw_chip_widgets.append((None, all_chip))
        for s in syms:
            chip = self._twitter_chip(
                s, counts.get(s, 0), self._tw_filter == s,
                lambda sym=s: self._twitter_set_filter(sym),
                removable=True)
            self.tw_chips_layout.addWidget(chip)
            self._tw_chip_widgets.append((s, chip))

        # TÜM satırları bir kez kur ve sakla; filtre değişiminde yalnızca
        # setVisible ile göster/gizle (hisse panelindeki _apply_visibility_filter
        # deseni — her filtre tıklamasında ~20 satırı yeniden yaratma).
        # Satır, eşleşen TÜM sembollerin listesiyle saklanır → çok sembollü tweet
        # her ilgili sembol filtresinde görünür.
        self._tw_rows = []          # [(syms_list, row_widget)]
        for tw in tweets:
            ms = syms_of(tw)
            unread = tw.get("id", "") in self._tw_hl
            user = self._tw_users.get(tw.get("author_id", ""), {})
            # Chip etiketinde ilk eşleşen sembolü göster (satır başına tek rozet).
            row = self._twitter_row(tw, user, unread, ms[0] if ms else "")
            self.twitter_layout.addWidget(row)
            self._tw_rows.append((ms, row))

        # "Gösterilecek tweet yok" etiketi (filtreye göre görünürlüğü ayarlanır)
        self._tw_empty_lbl = QLabel("Gösterilecek tweet yok.")
        self._tw_empty_lbl.setFont(_f(11))
        self._tw_empty_lbl.setAlignment(Qt.AlignCenter)
        self._tw_empty_lbl.setStyleSheet(
            f"color: {C_TEXT3}; background: transparent; padding: 18px 0;")
        self.twitter_layout.addWidget(self._tw_empty_lbl)

        self._twitter_apply_filter_visibility()

        n = len(self._tw_hl)
        self.lbl_tw_count.setText(str(n))
        self.lbl_tw_count.setVisible(n > 0)
        self.btn_tw_read.setVisible(n > 0)
        self.lbl_twitter_status.setText(f"{len(tweets)} tweet" if tweets else "")

    def _twitter_apply_filter_visibility(self):
        """Aktif filtreye göre satır görünürlüğü + çip renklerini güncelle.

        Widget'ları YOK ETMEZ; yalnızca setVisible/setStyleSheet — filtre
        tıklaması ucuz olsun (tam yeniden inşa yok).
        """
        shown = 0
        for syms, row in getattr(self, "_tw_rows", []):
            # Çok sembollü tweet her ilgili sembol filtresinde görünür.
            visible = self._tw_filter is None or self._tw_filter in syms
            row.setVisible(visible)
            if visible:
                shown += 1
        if hasattr(self, "_tw_empty_lbl"):
            self._tw_empty_lbl.setVisible(shown == 0)
        # Çip aktiflik renklerini güncelle (widget yeniden kurmadan)
        for sym, chip in getattr(self, "_tw_chip_widgets", []):
            active = (sym == self._tw_filter) or (sym is None and self._tw_filter is None)
            self._twitter_style_chip(chip, active)

    def _twitter_set_filter(self, sym):
        self._tw_filter = sym
        # Tam yeniden inşa yerine yalnızca görünürlük/renk güncelle.
        if getattr(self, "_tw_rows", None) is not None:
            self._twitter_apply_filter_visibility()
        else:
            self._twitter_render()

    def _twitter_load(self):
        """Sekme açılışı — ağ çağrısı arka plan thread'de, UI bloke olmaz."""
        token = self._twitter_token()
        if not token:
            self._tw_tweets = []
            self._twitter_render()
            self.lbl_twitter_status.setText("token yok")
            return
        if getattr(self, "_tw_loading", False):
            return
        self._tw_loading = True
        self.lbl_twitter_status.setText("yükleniyor…")
        # twitter_client kendi thread'inde çalışır; sonucu sinyalle ana thread'e geçir.
        twitter_client.fetch_recent(
            self._twitter_query(),
            lambda result: self.tw_load_result.emit(result),
        )

    def _twitter_load_apply(self, result):
        """Ana thread — yükleme sonucunu state'e uygula ve render et (thread-safe)."""
        self._tw_loading = False
        tweets, users, err = result
        if err is not None:
            self._tw_tweets = []
            self._twitter_render()
            self.lbl_twitter_status.setText(err)
            return
        self._tw_tweets = tweets
        self._tw_users = users
        incoming = {tw.get("id", "") for tw in self._tw_tweets}
        had_seen = bool(self._tw_seen)
        new_ids, self._tw_seen = compute_unread(
            incoming, self._tw_seen, active=(self._mode == 3))
        self._prune_tw_seen(incoming)
        if had_seen:
            self._tw_hl = new_ids
            if self._mode != 3:
                self._tw_unread |= new_ids
        else:
            self._tw_hl = set()
        self._tw_last = datetime.now().strftime("%H:%M")
        self.lbl_tw_time.setText(f"son: {self._tw_last}")
        self._twitter_render()
        self._update_tab_badge()

    def _prune_tw_seen(self, incoming):
        """_tw_seen sınırsız büyümesin: son görülenler + gelenlerle sınırla.

        Twitter search yalnızca son ~20 tweet'i döndürür; eski id'leri tutmanın
        faydası yok. Üst sınırı aşınca gelenleri koruyup gerisini buda.
        """
        _CAP = 500
        if len(self._tw_seen) > _CAP:
            # gelenleri kesin koru, kalanı sınıra kadar doldur
            keep = set(incoming)
            for tid in self._tw_seen:
                if len(keep) >= _CAP:
                    break
                keep.add(tid)
            self._tw_seen = keep

    def _twitter_poll(self):
        token = self._twitter_token()
        if not token:
            return
        # result = (ids, err). Eskiden yalnızca err is None dalı emit ediliyordu;
        # hata (rate-limit/500/ağ) sessizce yutuluyordu — durum güncellenmez,
        # kullanıcı arızayı görmezdi. Artık her iki dalı da ana thread'e geçir.
        twitter_client.fetch_ids(
            self._twitter_query(),
            lambda result: (
                self.tw_poll_result.emit(result[0])
                if result[1] is None
                else self.tw_poll_error.emit(str(result[1]))
            ),
        )

    def _twitter_poll_error(self, err):
        """Ana thread — poll hatasını kullanıcıya göster (sessiz yutma yok)."""
        # Sekme açıkken görünür durum çubuğuna yaz; kapalıyken sadece logla
        # (rozet zaten güncellenmedi). Backoff yok ama en azından görünür.
        log.info("twitter poll hatası: %s", err)
        if self._mode == 3 and hasattr(self, "lbl_tw_time"):
            self.lbl_tw_time.setText(f"poll hatası: {err}")

    def _twitter_poll_apply(self, incoming):
        """Ana thread — poll sonucunu state'e uygula (thread-safe)."""
        new_ids, self._tw_seen = compute_unread(
            incoming, self._tw_seen, active=(self._mode == 3))
        self._prune_tw_seen(incoming)
        if new_ids and self._mode != 3:
            self._tw_unread |= new_ids
            self._tw_hl |= new_ids
            self._update_tab_badge()

    # ── Panel aç/kapat ──────────────────────────────────────────────────
    def _quit_menu(self, event):
        m = _menu(self)
        m.addAction("Uygulamayı Kapat", QApplication.instance().quit)
        m.exec(event.globalPosition().toPoint())

    def _toggle(self, mode):
        closing = (self._mode == mode)
        if closing:
            if self._pinned or self._floating:
                return
            self._mode = 0
            target_w = 0
        else:
            prev = self._mode
            self._mode = mode
            self.stocks_page.setVisible(mode == 1)
            self.notes_page.setVisible(mode == 2)
            self.twitter_page.setVisible(mode == 3)
            if mode == 1 and prev != 1:
                self._stocks_refresh()
                QTimer.singleShot(1500, self._rsi_refresh)
            if mode == 2 and prev != 2:
                self._notes_load()
            if mode == 3 and prev != 3:
                self._twitter_load()
            if mode == 3:
                self._tw_unread.clear()
                self._update_tab_badge()
            target_w = PANEL_W
        self._paint_tab(self.tab_stock, self._mode == 1)
        self._paint_tab(self.tab_notes, self._mode == 2)
        self._paint_tab(self.tab_twitter, self._mode == 3)
        self._anim.stop()
        self._anim.setStartValue(min(self.panel.maximumWidth(), PANEL_W))
        self._anim.setEndValue(target_w)
        self._anim.start()

    def _modal_open(self):
        """Açık bir modal/popup sheet var mı? (Hisse ekle/Hedef/Bölüm/Not başlığı)

        Sheet'ler (_SheetDialog) exec() ile modal açılır ve ana panelin SOLUNDA
        ayrı top-level pencere olurlar. 'Dışarı tıklama = kapat' mantığı bunu
        hesaba katmazsa: sheet key window olunca ana pencere WindowDeactivate
        alır ve panel arkadan kapanır; sheet içine tıklama da eventFilter'da
        'panel dışı' sayılıp paneli kapatır. Sonuç: VARSAYILAN (floating kapalı)
        durumda 'Hisse ekle' açınca panel kaybolur, eklenen hisse görünmez.
        """
        app = QApplication.instance()
        return bool(app.activeModalWidget() or app.activePopupWidget())

    def changeEvent(self, event):
        if (event.type() == QEvent.WindowDeactivate and self._mode != 0
                and not self._pinned and not self._floating
                and not self._modal_open()):
            self._toggle(self._mode)
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.MouseButtonPress and self._mode != 0
                and not self._pinned and not self._floating
                and not self._modal_open()):
            gp = event.globalPosition().toPoint()
            if not self.geometry().contains(gp):
                self._toggle(self._mode)
        return super().eventFilter(obj, event)

    def _install_global_mouse_monitor(self):
        if not _APPKIT_OK:
            return
        try:
            mask = (1 << 1) | (1 << 3)  # NSLeftMouseDown | NSRightMouseDown

            def handler(nsevent):
                if (self._mode == 0 or self._pinned or self._floating
                        or self._modal_open()):
                    return
                loc = _NSEvent.mouseLocation()
                sh = self._current_sc.height() + self._current_sc.y()
                if not self.geometry().contains(QPoint(int(loc.x), int(sh - loc.y))):
                    QTimer.singleShot(0, lambda m=self._mode: self._toggle(m) if self._mode != 0 else None)

            self._ns_monitor = _NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)
            # Global monitor olay-tabanlı çalışıyor; 150ms polling yedeğine gerek yok.
            if self._ns_monitor is not None and hasattr(self, "_outside_click_timer"):
                self._outside_click_timer.stop()
        except Exception as e:
            log.warning("global mouse monitor hatası: %s", e)

    def _check_outside_click(self):
        if (self._mode == 0 or not _APPKIT_OK or self._pinned or self._floating
                or self._modal_open()):
            return
        try:
            buttons = _NSEvent.pressedMouseButtons()
            if not (buttons & 0b11):
                self._was_pressed = False
                return
            if getattr(self, '_was_pressed', False):
                return
            self._was_pressed = True
            loc = _NSEvent.mouseLocation()
            sh = self._current_sc.height() + self._current_sc.y()
            pt = QPoint(int(loc.x), int(sh - loc.y))
            if not self.geometry().contains(pt):
                self._toggle(self._mode)
        except Exception:
            pass


    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.lbl_empty:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _rebuild_rows(self):
        # Rebuild widget'ları yok eder; sparkline + RSI geçmişini koru
        for sym, row in self.rows.items():
            sp = getattr(row, "spark", None)
            if sp is not None and sp._points:
                self._spark_history[sym] = list(sp._points)

        self.rows.clear()
        self.headers.clear()
        self.cards.clear()
        self._sections = []          # [(uid, section_widget, card_widget, [row's])]
        self.lbl_empty.setParent(None)
        self._clear_layout(self.rows_layout)

        order = []
        groups = group_stocks(self.stocks)   # [(sep_uid or None, [stock dicts])]

        for uid, items in groups:
            if uid is None and not items:
                continue
            section = QWidget()
            sv = QVBoxLayout(section)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(2)

            collapsed = self._collapsed_sections.get(uid, False) if uid else False
            if uid is not None:
                header = GroupHeader(uid, len(items), collapsed)
                header.collapse_toggled.connect(self._on_collapse_toggled)
                header.rename_requested.connect(self._rename_separator)
                header.remove_requested.connect(self._remove_stock)
                header.move_requested.connect(self._move_stock)
                sv.addWidget(header)
                self.headers[uid] = header
                order.append((uid, header))

            card = QWidget()
            card.setObjectName("card")
            card.setStyleSheet("#card { background: transparent; }")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)

            section_rows = []
            # TÜM satırları oluştur (filtreye bakmadan); görünürlük ayrı ele
            # alınır. Böylece arama her tuşta widget yok edip yeniden kurmaz.
            for i, s in enumerate(items):
                sym = s["symbol"]
                row = StockRow(sym, s.get("entry"), s.get("exit"))
                hist = self._spark_history.get(sym)
                if hist:
                    row.spark.restore(hist)
                rsi_cached = self._rsi_cache.get(sym)
                if rsi_cached:
                    row.update_rsi(rsi_cached)
                row.remove_requested.connect(self._remove_stock)
                row.levels_changed.connect(self._update_levels)
                cv.addWidget(row)
                self.rows[sym] = row
                order.append((sym, row))
                section_rows.append((sym, row))

            if uid is not None:
                self.cards[uid] = card
            sv.addWidget(card)
            self.rows_layout.addWidget(section)
            self._sections.append((uid, section, card, section_rows))

        self.host.set_order(order)
        self.rows_layout.addWidget(self.lbl_empty)
        self._apply_visibility_filter()

    def _apply_visibility_filter(self):
        """Arama filtresi + katlama durumuna göre satır/kart görünürlüğü ayarla.

        Widget'ları YOK ETMEZ; yalnızca setVisible() — arama her tuşta ucuz.
        """
        any_visible = False
        for uid, section, card, section_rows in self._sections:
            collapsed = self._collapsed_sections.get(uid, False) if uid else False
            visible_rows = 0
            for sym, row in section_rows:
                match = (not self._filter) or (self._filter in sym.upper())
                row.setVisible(match)
                if match:
                    visible_rows += 1
            if visible_rows > 0:
                any_visible = True
            card.setVisible(visible_rows > 0 and not collapsed)
            section.setVisible(visible_rows > 0 or (uid is not None and not self._filter))

        self.lbl_empty.setVisible(not any_visible)
        self.lbl_empty.setText(
            "Eşleşme yok\nEklemek için Enter'a bas." if self._filter
            else "Takip listen boş\nSembolü yaz, listeden ekle."
        )

    # ── Arama ───────────────────────────────────────────────────────────
    def _on_search(self, text):
        # Anlık: sadece "Ekle" butonu görünürlüğü (ucuz)
        q = text.strip().upper()
        self._filter = q
        known = any(s["symbol"].upper() == q for s in self.stocks)
        # Buton yalnızca bilinen ama henüz eklenmemiş sembolde görünsün.
        self.btn_add_inline.setVisible(
            len(q) >= 3 and not known and sym_universe.is_known(q)
        )
        # Gecikmeli: liste yeniden kurma (200ms yazma durunca)
        self._search_timer.start(200)

    def _apply_search_filter(self):
        # Widget'lar zaten kurulu; yalnızca görünürlük değişir (ucuz).
        self._apply_visibility_filter()

    def _add_from_search(self):
        sym = self.search.text().strip().upper()
        if not sym:
            return
        if not sym_universe.is_known(sym):
            # Sessizce yutma — kullanıcıya bilinmeyen sembolü bildir.
            self.lbl_stock_status.setText(f"Bilinmeyen sembol: {sym}")
            return
        if not any(s["symbol"] == sym for s in self.stocks):
            self.stocks.append({"symbol": sym, "entry": None, "exit": None})
            save_stocks(self.stocks)
        self.search.clear()
        self._filter = ""
        self._rebuild_rows()
        self._stocks_refresh()

    # ── Sürükle-bırak ───────────────────────────────────────────────────
    def _on_dropped(self, moved, target, is_header):
        # Başlığa bırakma → hisse o bölümün İLK öğesi (başlığın ardına).
        # Satır arasına bırakma → eski "hedefin önüne" davranışı korunur.
        new_order = reorder(self.stocks, moved, target, after=is_header)
        if new_order == self.stocks:
            return
        self.stocks = new_order
        # Katlanmış bir bölüm başlığına bırakıldıysa bölümü aç ki hisse görünsün.
        if is_header and self._collapsed_sections.get(target):
            self._collapsed_sections[target] = False
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._apply_cached_prices()

    # ── Hisse işlemleri ─────────────────────────────────────────────────
    def _add_stock(self):
        existing = [s["symbol"] for s in self.stocks]
        dlg = StockPickerSheet(existing=existing, parent=self)
        dlg.exec()
        sym = (dlg.value or "").upper()
        if not sym or any(s["symbol"] == sym for s in self.stocks):
            return
        self.stocks.append({"symbol": sym, "entry": None, "exit": None})
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._stocks_refresh()

    def _add_separator(self):
        dlg = TextSheet("Yeni bölüm", "Bölüm adı", parent=self)
        dlg.exec()
        if dlg.value is None:
            return
        counter = next_separator_counter(self.stocks)
        self.stocks.append({"symbol": make_sep_symbol(dlg.value, counter), "entry": None, "exit": None})
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _rename_separator(self, symbol):
        name, counter = _parse_sep_symbol(symbol)
        dlg = TextSheet("Bölümü yeniden adlandır", "Yeni ad", default=name, parent=self)
        dlg.exec()
        if dlg.value is None:
            return
        new_symbol = make_sep_symbol(dlg.value, counter)
        for s in self.stocks:
            if s["symbol"] == symbol:
                s["symbol"] = new_symbol
                break
        if symbol in self._collapsed_sections:
            self._collapsed_sections[new_symbol] = self._collapsed_sections.pop(symbol)
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._apply_cached_prices()

    def _move_stock(self, symbol, direction):
        idx = next((i for i, s in enumerate(self.stocks) if s["symbol"] == symbol), None)
        if idx is None:
            return
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.stocks)):
            return
        self.stocks[idx], self.stocks[new_idx] = self.stocks[new_idx], self.stocks[idx]
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._apply_cached_prices()

    def _on_collapse_toggled(self, symbol, is_collapsed):
        self._collapsed_sections[symbol] = is_collapsed
        card = self.cards.get(symbol)
        if card is not None:
            card.setVisible(not is_collapsed)
            return
        self._rebuild_rows()
        self._apply_cached_prices()

    def _remove_stock(self, symbol):
        self.stocks = [s for s in self.stocks if s["symbol"] != symbol]
        # Kaldırılan sembolün önbelleklerini de temizle (sınırsız birikmesin).
        self._rsi_cache.pop(symbol, None)
        self._spark_history.pop(symbol, None)
        # _last_data'yı da temizle: aksi halde aynı sembol silinip yeniden
        # eklenince, ilk yeni fetch gelmeden _apply_cached_prices bayat (stale)
        # fiyatı gerçek zamanlıymış gibi yeni satıra basar (rsi_cache/spark ile
        # tutarsız temizlikti).
        if hasattr(self, "_last_data"):
            self._last_data.pop(symbol, None)
        if symbol in self._collapsed_sections:
            self._collapsed_sections.pop(symbol, None)
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._apply_cached_prices()

    def _update_levels(self, symbol, entry, exit_price):
        for s in self.stocks:
            if s["symbol"] == symbol:
                s["entry"] = entry
                s["exit"] = exit_price
                break
        save_stocks(self.stocks)

    # ── Veri ────────────────────────────────────────────────────────────
    def _stocks_refresh(self):
        symbols = [s["symbol"] for s in self.stocks if not s["symbol"].startswith(_SEP_SYMBOL)]
        if not symbols or self._fetching:
            return
        self._fetching = True
        self.lbl_stock_status.setText("Güncelleniyor…")
        fetch_all(symbols, lambda r: self._signals.data_signal.emit(r))

    def apply_data(self, results):
        try:
            self._last_data = {i["symbol"]: i for i in (results or [])}
            self.lbl_stock_status.setText(datetime.now().strftime("%H:%M"))
            self._apply_cached_prices()
        finally:
            self._fetching = False

    def _apply_cached_prices(self):
        for sym, item in getattr(self, "_last_data", {}).items():
            if sym in self.rows:
                self.rows[sym].update_data(item["price"], item["change_pct"])

    def _rsi_refresh(self):
        # Yalnızca hisse paneli açıkken RSI çek — kapalıyken boşuna WS açma.
        if self._mode != 1:
            return
        syms = [
            s["symbol"] for s in self.stocks
            if not s["symbol"].startswith(_SEP_SYMBOL)
        ]
        if not syms:
            return
        if getattr(self, "_rsi_fetching", False):
            return
        self._rsi_fetching = True

        def _fetch():
            try:
                try:
                    # Tek WS bağlantısında tüm semboller için RSI (sembol başına
                    # ayrı bağlantı yok).
                    out = fetch_tv_rsi_bulk(syms)
                except Exception as e:
                    log.warning("RSI toplu çekim hatası: %s", e)
                    out = {}
                for s in syms:
                    rsi = out.get(s.upper())
                    if rsi:
                        self._signals.rsi_signal.emit(s, rsi)
            finally:
                # Bayrağı worker'da DEĞİL, ana thread'de kapat: rsi_done sinyali
                # _on_rsi_done'ı ana thread'de çalıştırır (thread-safe re-entrancy).
                # finally: emit döngüsü/başka bir yol istisna atsa bile bayrak
                # kalıcı True kalıp gelecek RSI yenilemelerini bloke etmesin.
                self.rsi_done.emit()
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_rsi_done(self):
        """Ana thread — RSI worker bitti, re-entrancy kilidini bırak."""
        self._rsi_fetching = False

    def apply_rsi(self, symbol, rsi):
        self._rsi_cache[symbol] = rsi
        if symbol in self.rows:
            self.rows[symbol].update_rsi(rsi)

    # ── Notlar ──────────────────────────────────────────────────────────
    def _notes_load(self):
        if getattr(self, "_notes_loading", False):
            return
        self._notes_loading = True
        self.lbl_notes_status.setText("Yükleniyor…")
        fetch_notes(lambda notes: self._signals.notes_signal.emit(notes))

    def apply_notes(self, notes):
        self._notes_loading = False
        if notes == "unconfigured":
            self._notes = []
            self._refresh_notes_list()
            self.lbl_notes_status.setText("Kurulmadı (GIST_ID/token yok)")
            return
        if notes is None:
            self.lbl_notes_status.setText("Bağlantı hatası")
            return
        # Uzak içerik geldiğinde, kullanıcının 1500ms debounce içinde yazdığı
        # bekleyen kaydı iptal ETME — aksi halde uzak liste yerel yazımı sessizce
        # ezer. Bekleyen kayıt varsa uzak içeriği uygulama, kullanıcının yazdığını
        # koru ve durumu bildir (veri kaybı yarışını önle).
        if self._save_timer.isActive():
            self.lbl_notes_status.setText("Yerel değişiklik korundu (kaydediliyor)")
            return
        # Gist içeriği dışarıdan (başka istemci/elle) bozulabilir; yalnızca
        # 'title'/'body' anahtarlı dict öğeleri kabul et — dict olmayan öğe
        # _refresh_notes_list'te AttributeError ile UI'ı çökertmesin.
        self._notes = sanitize_notes(notes)
        self._refresh_notes_list()
        self.lbl_notes_status.setText("Yüklendi")

    def _refresh_notes_list(self):
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        for n in self._notes:
            self.notes_list.addItem(n.get("title", "—"))
        self.notes_list.blockSignals(False)
        # Boş durum: liste boşsa editörü kapat, ipucu göster.
        if not self._notes:
            self._current_note = None
            self.notes_editor.setEnabled(False)
            self.notes_editor.blockSignals(True)
            self.notes_editor.clear()
            self.notes_editor.setPlaceholderText("Not yok — '+ Not' ile ekleyin.")
            self.notes_editor.blockSignals(False)
            return
        if self._current_note is not None and self._current_note < len(self._notes):
            self.notes_list.setCurrentRow(self._current_note)
        else:
            # İlk açılış (henüz seçim yok) veya geçersiz index: ilk notu otomatik
            # seç ki editör boş/pasif kalmasın (kullanıcı 'notlarım nerede?' demesin).
            self._current_note = 0
            self.notes_list.setCurrentRow(0)

    def _note_selected(self, row):
        if row < 0 or row >= len(self._notes):
            return
        self._current_note = row
        self.notes_editor.setEnabled(True)
        self.notes_editor.blockSignals(True)
        self.notes_editor.setPlainText(self._notes[row].get("body", ""))
        self.notes_editor.blockSignals(False)

    def _note_text_changed(self):
        if self._current_note is None:
            return
        self._notes[self._current_note]["body"] = self.notes_editor.toPlainText()
        self.lbl_notes_status.setText("Değişiklik var")
        self._save_timer.start(1500)

    def _notes_save_now(self):
        self.lbl_notes_status.setText("Kaydediliyor…")
        def _on_saved(ok):
            if ok == "unconfigured":
                msg = "Kurulmadı (GIST_ID/token yok)"
            elif ok:
                msg = "Kaydedildi"
            else:
                msg = "Kaydetme hatası!"
            QTimer.singleShot(0, lambda: self.lbl_notes_status.setText(msg))
        save_notes(self._notes, _on_saved)

    def _add_note(self):
        dlg = TextSheet("Yeni not", "Not başlığı", parent=self)
        dlg.exec()
        if not dlg.value:
            return
        self._notes.append({"title": dlg.value, "body": ""})
        self._current_note = len(self._notes) - 1
        self._refresh_notes_list()
        self._notes_save_now()

    def _rename_note(self, item):
        row = self.notes_list.row(item)
        if row < 0 or row >= len(self._notes):
            return
        dlg = TextSheet("Notu yeniden adlandır", "Yeni ad",
                        default=self._notes[row].get("title", ""), parent=self)
        dlg.exec()
        if not dlg.value:
            return
        self._notes[row]["title"] = dlg.value
        self._refresh_notes_list()
        self._notes_save_now()

    def _delete_note(self):
        if self._current_note is None:
            return
        self._notes.pop(self._current_note)
        self._current_note = None
        self._refresh_notes_list()
        self._notes_save_now()
