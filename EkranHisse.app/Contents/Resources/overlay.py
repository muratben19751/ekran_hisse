"""EkranHisse — Yoğun HUD (tasarım 3c).

main.py, data_fetcher.py, notes_api_client.py ve stocks.json biçimi DEĞİŞMEDİ.
Sadece bu dosya eski overlay.py'nin yerine kopyalanır.
"""

import json
import os
import subprocess
import threading
import urllib.request
import urllib.parse
import urllib.error

try:
    from AppKit import NSEvent as _NSEvent, NSScreen as _NSScreen
    _APPKIT_OK = True
except Exception:
    _APPKIT_OK = False

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal, QMimeData, QPoint, QEvent
)
from PySide6.QtGui import QFont, QPainter, QColor, QDrag, QPixmap, QPen, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication,
    QSizePolicy, QMenu, QListWidget, QTextEdit, QLineEdit, QDialog,
    QScrollArea, QFrame,
)

from data_fetcher import fetch_all, fetch_tv_rsi
from notes_api_client import fetch_notes, save_notes
import config
from logic import (
    tr_number, parse_price, parse_sep_symbol, twitter_query,
    symbol_of_tweet, compute_unread, group_stocks,
    next_separator_counter, reorder,
)

STOCKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocks.json")
TW_SYMBOLS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tw_symbols.json")
REFRESH_INTERVAL_MS = 60_000

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
C_TRACK     = "rgba(255, 255, 255, 32)"
C_SHEET_BG  = "rgba(44, 44, 46, 246)"
C_TINT_TGT  = "rgba(255, 214, 10, 20)"
C_TINT_NEW  = "rgba(10, 132, 255, 20)"

MIME_ROW = "application/x-ekranhisse-symbol"
_SEP_SYMBOL = "---"


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


def _tw_ago(iso):
    """'2026-07-31T11:02:00.000Z' → '12dk' / '3sa' / '2g'."""
    if not iso:
        return ""
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[11:16]
    secs = (datetime.now(timezone.utc) - t).total_seconds()
    if secs < 60:
        return "şimdi"
    if secs < 3600:
        return f"{int(secs // 60)}dk"
    if secs < 86400:
        return f"{int(secs // 3600)}sa"
    return f"{int(secs // 86400)}g"


def _main_screen():
    return QApplication.primaryScreen().geometry()


def _boost_level(win, level=1002):
    try:
        import objc
        ns_view = objc.objc_object(c_void_p=int(win.winId()))
        ns_win = ns_view.window()
        ns_win.setLevel_(level)
        ns_win.setHidesOnDeactivate_(False)
        ns_win.makeKeyAndOrderFront_(None)
    except Exception:
        pass


def load_stocks():
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
    # eksik "symbol" alanı olan bozuk kayıtları ele
    return [s for s in data if isinstance(s, dict) and "symbol" in s]


def save_stocks(stocks):
    try:
        with open(STOCKS_FILE, "w") as f:
            json.dump(stocks, f, ensure_ascii=False)
    except OSError:
        pass


def load_tw_symbols():
    """𝕏 takip sembolleri; dosya yoksa/bozuksa varsayılan ['TTKOM']."""
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
    try:
        with open(TW_SYMBOLS_FILE, "w") as f:
            json.dump(symbols, f, ensure_ascii=False)
    except OSError:
        pass


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
        QTimer.singleShot(0, lambda: _boost_level(self))


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
        self.value = self.inp.text().strip()
        self.accept()


_BIST_SYMBOLS = [
    "ACSEL","ADEL","ADESE","AEFES","AFYON","AGESA","AGHOL","AGYO","AHGAZ","AHSGY",
    "AKBNK","AKCNS","AKFGY","AKGRT","AKINM","AKSA","AKSEL","AKSEN","AKSGY","AKSUE",
    "AKTIF","ALARK","ALBRK","ALFAS","ALGYO","ALKA","ALKIM","ALKLC","ALMAD","ALTNY",
    "ANELE","ANGEN","ANHYT","ANSGR","ARASE","ARCLK","ARDYZ","ARENA","ARSAN","ARTMS",
    "ARZUM","ASELS","ASGYO","ASTOR","ASUZU","ATAGY","ATAKP","ATATP","ATEKS","ATLAS",
    "ATSYH","AVHOL","AVOD","AYCES","AYEN","AYES","AZTEK","BAGFS","BAKAB","BALAT",
    "BANVT","BARMA","BASCM","BASGZ","BAYRK","BERA","BEYAZ","BFREN","BIMAS","BIOEN",
    "BIZIM","BJKAS","BLCYT","BNTAS","BOSSA","BRISA","BRKO","BRKVY","BRMEN","BRSAN",
    "BRYAT","BSOKE","BTCIM","BUCIM","BURCE","BURVA","BVSAN","CANTE","CASA","CCOLA",
    "CELHA","CEMAS","CEMTS","CENTA","CIMSA","CLEBI","CMENT","CONSE","COSMO","CRFSA",
    "CUSAN","CVKMD","CWENE","DAGHL","DAPGM","DARDL","DENGE","DERHL","DERIM","DESA",
    "DESPC","DEVA","DGATE","DGGYO","DGNMO","DITAS","DJIST","DMSAS","DNISI","DOAS",
    "DOBUR","DOCO","DOGUB","DOHOL","DOMCO","DOPA","DPAZR","DRDOC","DTRND","DURDO",
    "DYOBY","DZGYO","EBEBK","EDATA","EDIP","EGEEN","EGEPO","EGGUB","EGPRO","EGSER",
    "EKGYO","ELITE","EMKEL","EMNIS","ENDKS","ENERY","ENGYO","ENJSA","ENKAI","ENSRI",
    "EPLAS","ERBOS","ERCB","ERDEM","ERDGD","EREGL","ERSU","ESCAR","ESCOM","ESEN",
    "ETILR","ETYAT","EUHOL","EUPWR","EUREN","EUYO","EYGYO","FADE","FENER","FMIZP",
    "FONET","FORMT","FORTE","FROTO","FZLGY","GARAN","GARFA","GEDIK","GEDZA","GENIL",
    "GENTS","GEREL","GESAN","GLBMD","GLCVY","GLRYH","GLYHO","GMTAS","GOKNR","GOLTS",
    "GOODY","GOZDE","GRSEL","GRTHO","GSDDE","GSDHO","GSRAY","GUBRF","GWIND","GZNMI",
    "HALKB","HATEK","HDFGS","HEDEF","HEKTS","HLGYO","HTTBT","HUNER","HURGZ","ICBCT",
    "ICUGS","IDEAS","IDGYO","IEYHO","IHEVA","IHGZT","IHLAS","IHLGM","IHYAY","IMASM",
    "INDES","INFO","INTEM","INVEO","INVES","IPEKE","ISBIR","ISCTR","ISDMR","ISFIN",
    "ISGSY","ISGYO","ISYAT","ITTFH","IZENR","IZFAS","IZINV","IZMDC","JANTS","KARMA",
    "KARTN","KATMR","KAYSE","KBORU","KCAER","KCHOL","KENT","KERVN","KFEIN","KGYO",
    "KLGYO","KLKIM","KLMSN","KLNMA","KLRHO","KLSER","KMPUR","KNFRT","KORDS","KOTON",
    "KOZAA","KOZAL","KRDMA","KRDMB","KRDMD","KRGYO","KRONT","KRPLS","KRSTL","KRTEK",
    "KRVGD","KSTUR","KTLEV","KTSKR","KUTPO","KUYAS","KVGYO","KZBGY","LIDER","LIDFA",
    "LINK","LMKDC","LOGO","LRSHO","LUKSK","MAALT","MAGEN","MAKIM","MAKTK","MANAS",
    "MARBL","MARKA","MARTI","MAVI","MEDTR","MEGAP","MEGMT","MEKAG","MEPET","MERCN",
    "MERIT","MERKO","METRO","METUR","MGROS","MHRGY","MIPAZ","MMCAS","MNDRS","MNDTR",
    "MOBTL","MOGAN","MSGYO","MTRKS","MTRYO","MZHLD","NATEN","NETAS","NIBAS","NTGAZ",
    "NTHOL","NUGYO","NUHCM","OBAMS","OBASE","ODAS","ODINE","OFSYM","OKCYM","ONCSM",
    "ONUR","ORGE","ORMA","OSMEN","OSTIM","OTKAR","OYAKC","OYAYO","OYLUM","OZGYO",
    "OZKGY","OZRDN","OZSUB","PAGYO","PAMEL","PAPIL","PCILT","PDPAS","PEGYO","PEKGY",
    "PENGD","PENTA","PETKM","PETUN","PGSUS","PINSU","PKART","PNLSN","POLHO","POLTK",
    "PRKAB","PRKME","PRZMA","PSDTC","PSGYO","PTOFS","PTHOL","RAKSN","RALYH","RAYSG",
    "RHEAG","RNPOL","RODRG","RTALB","RUBNS","RYGYO","RYSAS","SAFKR","SAGYO","SAHOL",
    "SANEL","SANFM","SANKO","SARKY","SASA","SAYAS","SDTTR","SEGMN","SEGYO","SEKFK",
    "SEKUR","SELEC","SELGD","SELVA","SEYKM","SILVR","SISE","SKBNK","SKTAS","SKYMD",
    "SMRTG","SNGYO","SNKRN","SODSN","SOKM","SONME","SRVGY","SUMAS","SUNEKS","SUWEN",
    "TABGD","TATEN","TATGD","TAVHL","TBORG","TCELL","TDGYO","TEKTU","TERA","TEZOL",
    "TGSAS","THYAO","TIRE","TKNSA","TKURU","TMSN","TOASO","TRCAS","TRGYO","TRILC",
    "TSPOR","TTKOM","TTRAK","TUCLK","TURGZ","TURSG","TZNGY","ULUFA","ULUSE","ULUUN",
    "UMPAS","UNLU","UNYEC","USAK","UZERB","VAKBN","VAKFN","VAKKO","VBTYZ","VERTU",
    "VERUS","VESBE","VESTL","VKGYO","VKFYO","VRGYO","WNDYR","XTCRT","XU030","XU050",
    "XU100","XBANK","XBLSM","XGIDA","XHOLD","XKMYA","XKURY","XMANA","XMESY","XSGRT",
    "XSPOR","XTEKS","XTRZM","XTUFE","XUMAL","XUSIN","XUTEK","XUHIZ","XAUUSD",
    "YATAS","YBTAS","YKBK","YKSLN","YUNSA","YYLGD","ZEDUR","ZOREN","ZORLU",
]


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
        self.lst.clear()
        for sym in _BIST_SYMBOLS:
            if sym in self._existing:
                continue
            if not q or sym.startswith(q):
                self.lst.addItem(sym)
        if self.lst.count() > 0:
            self.lst.setCurrentRow(0)

    def _ok(self):
        selected = self.lst.currentItem()
        typed = self.inp.text().strip().upper()
        self.value = selected.text() if selected else typed
        if self.value:
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

    def _num(self, text):
        text = text.strip()
        if not text:
            return None
        try:
            return _parse_price(text)
        except ValueError:
            return None

    def _save(self):
        self.result_value = ("save", self._num(self.inp_entry.text()), self._num(self.inp_exit.text()))
        self.accept()

    def _clear(self):
        self.result_value = ("clear",)
        self.accept()


# ── Hedef barı ──────────────────────────────────────────────────────────────
class TargetBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._entry = self._exit = self._price = None

    def set_levels(self, entry, exit_price, price):
        self._entry, self._exit, self._price = entry, exit_price, price
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        w, h = self.width(), self.height()
        p.setBrush(QColor(255, 255, 255, 32))
        p.drawRoundedRect(0, 0, w, h, 2, 2)
        if self._entry is None or self._exit is None or self._price is None:
            p.end()
            return
        lo, hi = min(self._entry, self._exit), max(self._entry, self._exit)
        frac = 1.0 if hi == lo else max(0.0, min(1.0, (self._price - lo) / (hi - lo)))
        reached = self._price >= hi
        p.setBrush(QColor(C_YELLOW if reached else C_GREEN))
        p.drawRoundedRect(0, 0, max(4, int(w * frac)), h, 2, 2)
        p.end()


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
        self._up = True

    def restore(self, points, up):
        self._points = list(points)[-self.MAX:]
        self._up = bool(up)
        self.update()

    def push(self, price, up):
        if price is None:
            return
        self._up = bool(up)
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
    reorder_started  = Signal(str)

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

        outer.addWidget(top)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._sync_target()

    def update_rsi(self, rsi: dict):
        pass
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
            self._reached = (
                self._price is not None and self._price >= max(self._entry, self._exit)
            )
            self.dot.setStyleSheet(
                f"background: {C_YELLOW if self._reached else C_GREEN}; border-radius: 2px;"
            )
            tip = f"Giriş {_tr(self._entry)}  ·  Çıkış {_tr(self._exit)}"
            if self._price is not None and self._entry:
                pnl = (self._price - self._entry) / self._entry * 100
                sign = "+" if pnl >= 0 else "−"
                tip += f"  ·  {sign}{_tr(abs(pnl), 1)}%"
            self.setToolTip(tip)
        else:
            self.setToolTip("")
        self._paint_bg()

    def update_data(self, price, change_pct, volume=None, avg_volume=None):
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
            self.spark.push(price, up)
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
        self.reorder_started.emit(self.symbol)
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
    # İlk yükleme (arka plan thread) sonucu: (tweets, users, hata_metni)
    tw_load_result = Signal(object)

    def __init__(self, signals):
        super().__init__()
        self._signals = signals
        self._mode = 0
        self._fetching = False
        self.stocks = load_stocks()
        self.rows = {}
        self.headers = {}
        self._spark_history = {}   # {symbol: (points, up)} — rebuild'ler arası korunur
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
        self._tw_symbols = load_tw_symbols()   # izlenen semboller (kalıcı)

        self._pinned = False

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

        sc = _main_screen()
        sc_avail = QApplication.primaryScreen().availableGeometry()
        win_h = sc_avail.height() // 2
        win_y = sc_avail.y() + sc_avail.height() - win_h
        self._anim = QPropertyAnimation(self.panel, b"maximumWidth")
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._anim.valueChanged.connect(lambda w: (
            self.setFixedWidth(TAB_W + w),
            self.move(sc.x() + sc.width() - TAB_W - w, self.y())
        ))
        self.panel.setMaximumWidth(0)
        self.setFixedSize(TAB_W, win_h)
        self.move(sc.x() + sc.width() - TAB_W, win_y)

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
        self.tw_load_result.connect(self._twitter_load_apply)

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
        if self._pinned:
            self.pin_btn.setStyleSheet(
                f"background: rgba(48,209,88,40); border-radius: 8px;"
                f" color: {C_GREEN};"
            )
        else:
            self.pin_btn.setStyleSheet(
                "background: transparent; color: rgba(235,235,245,100);"
            )

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

        self.pin_btn = QLabel("📌")
        self.pin_btn.setFixedSize(18, 18)
        self.pin_btn.setAlignment(Qt.AlignCenter)
        self.pin_btn.setFont(_f(11))
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setToolTip("Sürekli açık tut")
        self._update_pin_style()
        self.pin_btn.mousePressEvent = lambda e: self._toggle_pin()

        status = QLabel(status_text)
        status.setFont(_f(10))
        status.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(self.pin_btn)
        h.addWidget(status)
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
        h.addWidget(title)
        h.addWidget(self.lbl_tw_count)
        h.addWidget(self.lbl_twitter_status)
        h.addStretch()
        h.addWidget(self.btn_tw_read)
        pnl.addWidget(head)

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

    def _twitter_chip(self, label, count, active, on_click, removable=False):
        w = QWidget()
        w.setCursor(Qt.PointingHandCursor)
        w.setObjectName("chip")
        bg = C_BLUE if active else "rgba(255,255,255,18)"
        fg = "#ffffff" if active else C_TEXT3
        w.setStyleSheet(
            f"#chip {{ background: {bg}; border-radius: 5px; }}"
            f"#chip:hover {{ background: {C_BLUE if active else 'rgba(255,255,255,34)'}; }}"
        )
        lay = QHBoxLayout(w)
        lay.setContentsMargins(7, 2, 7 if not removable else 3, 3)
        lay.setSpacing(4)
        lbl = QLabel(label)
        lbl.setFont(_f(10, QFont.DemiBold))
        lbl.setStyleSheet(f"color: {fg}; background: transparent;")
        cnt = QLabel(str(count))
        cnt.setFont(_f(10))
        cnt.setStyleSheet(f"color: {fg if active else C_TEXT4}; background: transparent;")
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

        def sym_of(tw):
            return symbol_of_tweet(tw.get("text", ""), syms)

        counts = {}
        for tw in tweets:
            s = sym_of(tw)
            if s:
                counts[s] = counts.get(s, 0) + 1

        self.tw_chips_layout.addWidget(self._twitter_chip(
            "Tümü", len(tweets), self._tw_filter is None,
            lambda: self._twitter_set_filter(None)))
        for s in syms:
            self.tw_chips_layout.addWidget(self._twitter_chip(
                s, counts.get(s, 0), self._tw_filter == s,
                lambda sym=s: self._twitter_set_filter(sym),
                removable=True))

        shown = [tw for tw in tweets
                 if self._tw_filter is None or sym_of(tw) == self._tw_filter]
        if not shown:
            lbl = QLabel("Gösterilecek tweet yok.")
            lbl.setFont(_f(11))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {C_TEXT3}; background: transparent; padding: 18px 0;")
            self.twitter_layout.addWidget(lbl)
        else:
            for tw in shown:
                unread = tw.get("id", "") in self._tw_hl
                user = self._tw_users.get(tw.get("author_id", ""), {})
                self.twitter_layout.addWidget(
                    self._twitter_row(tw, user, unread, sym_of(tw)))

        n = len(self._tw_hl)
        self.lbl_tw_count.setText(str(n))
        self.lbl_tw_count.setVisible(n > 0)
        self.btn_tw_read.setVisible(n > 0)
        self.lbl_twitter_status.setText(f"{len(tweets)} tweet" if tweets else "")

    def _twitter_set_filter(self, sym):
        self._tw_filter = sym
        self._twitter_render()

    def _twitter_load(self):
        """Sekme açılışı — ağ çağrısı arka plan thread'de, UI bloke olmaz."""
        token = self._twitter_token()
        if not token:
            self._tw_tweets = []
            self._twitter_render()
            self.lbl_twitter_status.setText("token yok")
            return
        self.lbl_twitter_status.setText("yükleniyor…")
        threading.Thread(target=self._twitter_load_worker, daemon=True).start()

    def _twitter_load_worker(self):
        """Arka plan thread — ağdan tweet çeker, sonucu sinyalle ana thread'e iletir."""
        token = self._twitter_token()
        if not token:
            return
        try:
            url = (
                "https://api.twitter.com/2/tweets/search/recent"
                f"?query={urllib.parse.quote(self._twitter_query())}&max_results=20"
                "&tweet.fields=created_at,author_id,text"
                "&expansions=author_id&user.fields=username,name"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            self.tw_load_result.emit((tweets, users, None))
        except urllib.error.HTTPError as e:
            self.tw_load_result.emit(([], {}, f"hata {e.code}"))
        except Exception:
            self.tw_load_result.emit(([], {}, "hata"))

    def _twitter_load_apply(self, result):
        """Ana thread — yükleme sonucunu state'e uygula ve render et (thread-safe)."""
        from datetime import datetime
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

    def _twitter_poll(self):
        threading.Thread(target=self._twitter_poll_worker, daemon=True).start()

    def _twitter_poll_worker(self):
        """Arka plan thread — SADECE ağdan id çeker, state'e dokunmaz."""
        token = self._twitter_token()
        if not token:
            return
        try:
            url = (
                "https://api.twitter.com/2/tweets/search/recent"
                f"?query={urllib.parse.quote(self._twitter_query())}&max_results=20"
                "&tweet.fields=id"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            incoming = {tw.get("id", "") for tw in data.get("data", [])}
            # State değişikliği ana thread'de yapılsın diye sinyalle ilet.
            self.tw_poll_result.emit(incoming)
        except Exception:
            pass

    def _twitter_poll_apply(self, incoming):
        """Ana thread — poll sonucunu state'e uygula (thread-safe)."""
        new_ids, self._tw_seen = compute_unread(
            incoming, self._tw_seen, active=(self._mode == 3))
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
            if self._pinned:
                return
            self._mode = 0
            target_w = 0
        else:
            prev = self._mode
            self._mode = mode
            self.stocks_page.setVisible(mode == 1)
            self.notes_page.setVisible(mode == 2)
            self.twitter_page.setVisible(mode == 3)
            if mode == 1 and prev == 0:
                self._stocks_refresh()
            if mode == 2 and prev == 0:
                self._notes_load()
            if mode == 3 and prev == 0:
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

    def changeEvent(self, event):
        if event.type() == QEvent.WindowDeactivate and self._mode != 0 and not self._pinned:
            self._toggle(self._mode)
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and self._mode != 0 and not self._pinned:
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
                if self._mode == 0 or self._pinned:
                    return
                loc = _NSEvent.mouseLocation()
                sh = _NSScreen.mainScreen().frame().size.height
                if not self.geometry().contains(QPoint(int(loc.x), int(sh - loc.y))):
                    QTimer.singleShot(0, lambda m=self._mode: self._toggle(m) if self._mode != 0 else None)

            self._ns_monitor = _NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)
            # Global monitor olay-tabanlı çalışıyor; 150ms polling yedeğine gerek yok.
            if self._ns_monitor is not None and hasattr(self, "_outside_click_timer"):
                self._outside_click_timer.stop()
        except Exception as e:
            print("global mouse monitor hatası:", e)

    def _check_outside_click(self):
        if self._mode == 0 or not _APPKIT_OK or self._pinned:
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
            sh = _NSScreen.mainScreen().frame().size.height
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
                self._spark_history[sym] = (list(sp._points), sp._up)

        self.rows.clear()
        self.headers.clear()
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

            visible_rows = 0
            for i, s in enumerate(items):
                sym = s["symbol"]
                if self._filter and self._filter not in sym.upper():
                    continue
                row = StockRow(sym, s.get("entry"), s.get("exit"))
                hist = self._spark_history.get(sym)
                if hist:
                    row.spark.restore(hist[0], hist[1])
                rsi_cached = self._rsi_cache.get(sym)
                if rsi_cached:
                    row.update_rsi(rsi_cached)
                row.remove_requested.connect(self._remove_stock)
                row.levels_changed.connect(self._update_levels)
                cv.addWidget(row)
                self.rows[sym] = row
                order.append((sym, row))
                visible_rows += 1

            card.setVisible(visible_rows > 0 and not collapsed)
            sv.addWidget(card)
            section.setVisible(visible_rows > 0 or (uid is not None and not self._filter))
            self.rows_layout.addWidget(section)

        self.host.set_order(order)
        self.rows_layout.addWidget(self.lbl_empty)
        self.lbl_empty.setVisible(not self.rows)
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
        self.btn_add_inline.setVisible(len(q) >= 3 and not known)
        # Gecikmeli: liste yeniden kurma (200ms yazma durunca)
        self._search_timer.start(200)

    def _apply_search_filter(self):
        self._rebuild_rows()
        self._apply_cached_prices()

    def _add_from_search(self):
        sym = self.search.text().strip().upper()
        if not sym:
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
        self.stocks.append({"symbol": f"{_SEP_SYMBOL}:{dlg.value}:{counter}", "entry": None, "exit": None})
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _rename_separator(self, symbol):
        name, counter = _parse_sep_symbol(symbol)
        dlg = TextSheet("Bölümü yeniden adlandır", "Yeni ad", default=name, parent=self)
        dlg.exec()
        if dlg.value is None:
            return
        new_symbol = f"{_SEP_SYMBOL}:{dlg.value}:{counter}"
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
        self._rebuild_rows()
        self._apply_cached_prices()

    def _remove_stock(self, symbol):
        self.stocks = [s for s in self.stocks if s["symbol"] != symbol]
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
        from datetime import datetime
        self._fetching = False
        self._last_data = {i["symbol"]: i for i in results}
        self.lbl_stock_status.setText(datetime.now().strftime("%H:%M"))
        self._apply_cached_prices()

    def _apply_cached_prices(self):
        for sym, item in getattr(self, "_last_data", {}).items():
            if sym in self.rows:
                self.rows[sym].update_data(
                    item["price"], item["change_pct"],
                    item.get("volume"), item.get("avg_volume")
                )

    def _rsi_refresh(self):
        syms = [
            s["symbol"] for s in self.stocks
            if not s["symbol"].startswith(_SEP_SYMBOL)
        ]
        sem = threading.Semaphore(4)
        for sym in syms:
            def _fetch(s=sym):
                with sem:
                    rsi = fetch_tv_rsi(s)
                self._signals.rsi_signal.emit(s, rsi)
            threading.Thread(target=_fetch, daemon=True).start()

    def apply_rsi(self, symbol, rsi):
        self._rsi_cache[symbol] = rsi
        if symbol in self.rows:
            self.rows[symbol].update_rsi(rsi)

    # ── Notlar ──────────────────────────────────────────────────────────
    def _notes_load(self):
        self.lbl_notes_status.setText("Yükleniyor…")
        fetch_notes(lambda notes: self._signals.notes_signal.emit(notes if notes else []))

    def apply_notes(self, notes):
        if notes is None:
            self.lbl_notes_status.setText("Bağlantı hatası")
            return
        self._notes = notes or []
        self._refresh_notes_list()
        self.lbl_notes_status.setText("Kaydedildi")

    def _refresh_notes_list(self):
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        for n in self._notes:
            self.notes_list.addItem(n.get("title", "—"))
        self.notes_list.blockSignals(False)
        if self._current_note is not None and self._current_note < len(self._notes):
            self.notes_list.setCurrentRow(self._current_note)
        else:
            self._current_note = None
            self.notes_editor.setEnabled(False)
            self.notes_editor.blockSignals(True)
            self.notes_editor.clear()
            self.notes_editor.blockSignals(False)

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
        save_notes(self._notes, lambda _: QTimer.singleShot(
            0, lambda: self.lbl_notes_status.setText("Kaydedildi")))

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
