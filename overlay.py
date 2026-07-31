"""EkranHisse — macOS Native görünüm (tasarım 1b).

main.py, data_fetcher.py, notes_api_client.py ve stocks.json biçimi DEĞİŞMEDİ.
Sadece bu dosya eski overlay.py'nin yerine kopyalanır.
"""

import json
import os

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal, QMimeData, QPoint, QEvent
)
from PySide6.QtGui import QFont, QPainter, QColor, QDrag, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication,
    QSizePolicy, QMenu, QListWidget, QTextEdit, QLineEdit, QDialog,
    QScrollArea, QFrame,
)

from data_fetcher import fetch_all
from notes_api_client import fetch_notes, save_notes

STOCKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocks.json")
REFRESH_INTERVAL_MS = 60_000

# ── Geometri ────────────────────────────────────────────────────────────────
PANEL_W = 320
TAB_W   = 32
TAB_H   = 56
TAB_GAP = 6
ANIM_MS = 220

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

MIME_ROW = "application/x-ekranhisse-symbol"
_SEP_SYMBOL = "---"


# ── Yardımcılar ─────────────────────────────────────────────────────────────
def _f(size, weight=QFont.Normal):
    f = QFont()          # macOS sistem yazı tipi (SF)
    f.setPointSize(size)
    f.setWeight(weight)
    return f


def _tr(v, d=2):
    """1234.5 → '1.234,50' (TR biçimi)."""
    s = f"{v:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _parse_price(val: str):
    v = val.strip()
    if ',' in v and '.' in v:
        v = v.replace('.', '').replace(',', '.')
    else:
        v = v.replace(',', '.')
    return float(v)


def _parse_sep_symbol(symbol: str):
    parts = symbol.split(":", 2)
    if len(parts) == 3:
        return parts[1], parts[2]
    if len(parts) == 2:
        return "", parts[1]
    return "", "0"


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
    if os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE) as f:
            data = json.load(f)
        if data and isinstance(data[0], str):
            return [{"symbol": s, "entry": None, "exit": None} for s in data]
        return data
    return []


def save_stocks(stocks):
    with open(STOCKS_FILE, "w") as f:
        json.dump(stocks, f)


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
    "RHEAG","RNPOL","RODRG","RTALB","RUBNS","RYGYO"," RYSMAN","SAFKR","SAGYO","SAHOL",
    "SANEL","SANFM","SANKO","SARKY","SASA","SAYAS","SDTTR","SEGMN","SEGYO","SEKFK",
    "SEKUR","SELEC","SELGD","SELVA","SEYKM","SILVR","SISE","SKBNK","SKTAS","SKYMD",
    "SMRTG","SNGYO","SNKRN","SODSN","SOKM","SONME","SRVGY","SUMAS","SUNEKS","SUWEN",
    "TABGD","TATEN","TATGD","TAVHL","TBORG","TCELL","TDGYO","TEKTU","TERA","TEZOL",
    "TGSAS","THYAO","TIRE","TKNSA","TKURU","TMSN","TOASO","TRCAS","TRGYO","TRILC",
    "TSPOR","TTKOM","TTRAK","TUCLK","TURGZ","TURSG","TZNGY","ULUFA","ULUSE","ULUUN",
    "UMPAS","UNLU","UNYEC","USAK","UZERB","VAKBN","VAKFN","VAKKO","VBTYZ","VERTU",
    "VERUS","VESBE","VESTEL","VKGYO","VKFYO","VRGYO","WNDYR","XTCRT","XU030","XU050",
    "XU100","XBANK","XBLSM","XGIDA","XHOLD","XKMYA","XKURY","XMANA","XMESY","XSGRT",
    "XSPOR","XTEKS","XTRZM","XTUFE","XUMAL","XUSIN","XUTEK","XTCRT","XUHIZ","XAUUSD",
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
class StockRow(QWidget):
    remove_requested = Signal(str)
    levels_changed   = Signal(str, object, object)
    reorder_started  = Signal(str)

    def __init__(self, symbol, entry=None, exit_price=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self._entry, self._exit, self._price = entry, exit_price, None
        self._press_pos = None
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("row")
        self.setStyleSheet(
            "#row { background: transparent; }"
            f"#row:hover {{ background: {C_ROW_HOVER}; }}"
        )
        self.setCursor(Qt.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 9)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.lbl_symbol = QLabel(symbol)
        self.lbl_symbol.setFont(_f(13, QFont.DemiBold))
        self.lbl_symbol.setStyleSheet(f"color: {C_TEXT}; background: transparent;")

        self.lbl_badge = QLabel("Hedef")
        self.lbl_badge.setFont(_f(10, QFont.DemiBold))
        self.lbl_badge.setStyleSheet(
            f"color: {C_YELLOW}; background: rgba(255,214,10,46);"
            " border-radius: 5px; padding: 2px 6px;"
        )
        self.lbl_badge.setVisible(False)

        self.lbl_price = QLabel("—")
        self.lbl_price.setFont(_f(13))
        self.lbl_price.setStyleSheet(f"color: {C_TEXT2}; background: transparent;")
        self.lbl_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_price.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lbl_pct = QLabel("—")
        self.lbl_pct.setFont(_f(11, QFont.DemiBold))
        self.lbl_pct.setAlignment(Qt.AlignCenter)
        self.lbl_pct.setMinimumWidth(58)
        self._set_pill(None)

        top.addWidget(self.lbl_symbol)
        top.addWidget(self.lbl_badge)
        top.addWidget(self.lbl_price)
        top.addWidget(self.lbl_pct)
        outer.addLayout(top)

        self.target_wrap = QWidget()
        tv = QVBoxLayout(self.target_wrap)
        tv.setContentsMargins(0, 0, 0, 2)
        tv.setSpacing(5)
        self.bar = TargetBar()
        tv.addWidget(self.bar)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(0)
        self.lbl_entry = QLabel("")
        self.lbl_pnl   = QLabel("")
        self.lbl_exit  = QLabel("")
        for lb in (self.lbl_entry, self.lbl_pnl, self.lbl_exit):
            lb.setFont(_f(11))
            lb.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        meta.addWidget(self.lbl_entry)
        meta.addStretch()
        meta.addWidget(self.lbl_pnl)
        meta.addStretch()
        meta.addWidget(self.lbl_exit)
        tv.addLayout(meta)
        outer.addWidget(self.target_wrap)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self._sync_target()

    # görünüm ------------------------------------------------------------
    def _set_pill(self, pct):
        if pct is None:
            self.lbl_pct.setText("—")
            self.lbl_pct.setStyleSheet(
                f"color: {C_TEXT3}; background: {C_CTRL}; border-radius: 6px; padding: 3px 7px;"
            )
            return
        up = pct >= 0
        self.lbl_pct.setText(("+" if up else "−") + _tr(abs(pct)) + "%")
        self.lbl_pct.setStyleSheet(
            f"color: {C_GREEN_INK if up else C_RED_INK};"
            f" background: {C_GREEN if up else C_RED};"
            " border-radius: 6px; padding: 3px 7px;"
        )

    def _sync_target(self):
        has = self._entry is not None and self._exit is not None
        self.target_wrap.setVisible(has)
        if not has:
            self.lbl_badge.setVisible(False)
            return
        self.bar.set_levels(self._entry, self._exit, self._price)
        self.lbl_entry.setText(_tr(self._entry))
        self.lbl_exit.setText(_tr(self._exit))
        if self._price is None:
            self.lbl_pnl.setText("")
            self.lbl_badge.setVisible(False)
            return
        reached = self._price >= max(self._entry, self._exit)
        self.lbl_badge.setVisible(reached)
        if self._entry:
            pnl = (self._price - self._entry) / self._entry * 100
            self.lbl_pnl.setText(("+" if pnl >= 0 else "−") + _tr(abs(pnl), 1) + "% hedefe")
            self.lbl_pnl.setStyleSheet(
                f"color: {C_YELLOW if reached else C_GREEN}; background: transparent;"
            )

    def update_data(self, price, change_pct):
        self._price = price
        self.lbl_price.setText("—" if price is None else "₺" + _tr(price))
        self._set_pill(change_pct)
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
        self.setFixedHeight(18)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(6)

        name, _ = _parse_sep_symbol(uid)
        self.lbl = QLabel((name or "Takip").upper())
        self.lbl.setFont(_f(11, QFont.DemiBold))
        self.lbl.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")

        self.chev = QLabel("›" if collapsed else "⌄")
        self.chev.setFont(_f(11))
        self.chev.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")

        self.cnt = QLabel(str(count))
        self.cnt.setFont(_f(11))
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
    dropped = Signal(str, object)   # taşınan sembol, hedef sembol (None = sona)

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
        for sym, w in self._order:
            if not w.isVisible():
                continue
            top_left = w.mapTo(self, QPoint(0, 0))
            if y < top_left.y() + w.height() / 2:
                return sym, top_left.y()
        return None, None

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME_ROW):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasFormat(MIME_ROW):
            return
        y = int(e.position().y())
        sym, top = self._target_at(y)
        if top is None:
            top = self.height() - 2
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
        target, _unused = self._target_at(int(e.position().y()))
        e.acceptProposedAction()
        self.dropped.emit(moved, target)


# ── Ana pencere ─────────────────────────────────────────────────────────────
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._mode = 0
        self._fetching = False
        self.stocks = load_stocks()
        self.rows = {}
        self.headers = {}
        self._collapsed_sections = {}
        self._filter = ""

        self._twitter_known_ids = set()
        self._twitter_alert = False
        self._twitter_blink_state = False

        self._notes = []
        self._current_note = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._notes_save_now)

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
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
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
        QTimer.singleShot(1000, self._notes_load)
        QTimer.singleShot(500, self._install_global_mouse_monitor)
        self._outside_click_timer = QTimer(self)
        self._outside_click_timer.timeout.connect(self._check_outside_click)
        self._outside_click_timer.start(100)

        self._twitter_poll_timer = QTimer(self)
        self._twitter_poll_timer.timeout.connect(self._twitter_poll)
        self._twitter_poll_timer.start(60_000)

        self._twitter_blink_timer = QTimer(self)
        self._twitter_blink_timer.timeout.connect(self._twitter_blink_tick)
        self._twitter_blink_timer.start(600)

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

    def _make_tab(self, glyph, mode):
        tab = QWidget()
        tab.setFixedSize(TAB_W, TAB_H)
        tab.setCursor(Qt.PointingHandCursor)
        tab.setObjectName(f"tab{mode}")
        lyt = QVBoxLayout(tab)
        lyt.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(glyph)
        lbl.setFont(_f(15))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background: transparent;")
        lyt.addWidget(lbl)
        tab._label = lbl
        tab._mode = mode
        tab.mousePressEvent = lambda e, m=mode: (
            self._quit_menu(e) if e.button() == Qt.RightButton else self._toggle(m)
        )
        self._paint_tab(tab, False)
        return tab

    def _paint_tab(self, tab, active, alert=False):
        if alert:
            bg = "#c0392b" if self._twitter_blink_state else "rgba(48,48,50,214)"
            border = "none"
        else:
            bg = C_BLUE if active else "rgba(48, 48, 50, 214)"
            border = "none" if active else f"1px solid {C_BORDER}"
        tab.setStyleSheet(
            f"#{tab.objectName()} {{ background: {bg}; border: {border}; border-right: none;"
            f" border-top-left-radius: {R_TAB}px; border-bottom-left-radius: {R_TAB}px; }}"
        )
        tab._label.setStyleSheet(
            f"color: {'#ffffff' if (active or alert) else C_TEXT2}; background: transparent;"
        )

    def _twitter_blink_tick(self):
        if not self._twitter_alert:
            return
        self._twitter_blink_state = not self._twitter_blink_state
        self._paint_tab(self.tab_twitter, self._mode == 3, alert=True)

    def _title_row(self, title):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 12, 14, 10)
        h.setSpacing(8)
        lbl = QLabel(title)
        lbl.setFont(_f(15, QFont.DemiBold))
        lbl.setStyleSheet(f"color: {C_TEXT}; background: transparent;")
        status = QLabel("")
        status.setFont(_f(11))
        status.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(status)
        return w, status

    # ── Hisse sayfası ───────────────────────────────────────────────────
    def _build_stocks_page(self):
        page = QWidget()
        pnl = QVBoxLayout(page)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        head, self.lbl_stock_status = self._title_row("Portföy")
        pnl.addWidget(head)

        # Arama + ekle
        search_wrap = QWidget()
        sw = QHBoxLayout(search_wrap)
        sw.setContentsMargins(14, 0, 14, 10)
        sw.setSpacing(0)
        field = QWidget()
        field.setObjectName("searchfield")
        field.setFixedHeight(28)
        field.setStyleSheet(
            f"#searchfield {{ background: {C_FIELD}; border-radius: 8px; }}"
        )
        fl = QHBoxLayout(field)
        fl.setContentsMargins(10, 0, 6, 0)
        fl.setSpacing(7)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara veya ekle")
        self.search.setFont(_f(12))
        self.search.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {C_TEXT}; }}"
        )
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._add_from_search)
        self.btn_add_inline = QPushButton("Ekle")
        self.btn_add_inline.setFont(_f(11, QFont.DemiBold))
        self.btn_add_inline.setFixedHeight(20)
        self.btn_add_inline.setCursor(Qt.PointingHandCursor)
        self.btn_add_inline.setStyleSheet(
            f"QPushButton {{ background: {C_BLUE}; color: #fff; border: none;"
            f" border-radius: 6px; padding: 0 9px; }}"
            f"QPushButton:hover {{ background: {C_BLUE_HOVER}; }}"
        )
        self.btn_add_inline.clicked.connect(self._add_from_search)
        self.btn_add_inline.setVisible(False)
        fl.addWidget(self.search)
        fl.addWidget(self.btn_add_inline)
        sw.addWidget(field)
        pnl.addWidget(search_wrap)

        # Liste
        self.host = RowsHost()
        self.rows_layout = QVBoxLayout(self.host)
        self.rows_layout.setContentsMargins(10, 0, 10, 4)
        self.rows_layout.setSpacing(14)
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.host.dropped.connect(self._on_dropped)

        scroll = QScrollArea()
        scroll.setWidget(self.host)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,45);"
            " border-radius: 3px; min-height: 24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        pnl.addWidget(scroll, 1)

        self.lbl_empty = QLabel("Takip listen boş\nSembolü yaz, listeden ekle.")
        self.lbl_empty.setFont(_f(12))
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
        self.rows_layout.addWidget(self.lbl_empty)

        # Alt bar
        bar = QWidget()
        bar.setObjectName("toolbar")
        bar.setStyleSheet(f"#toolbar {{ border-top: 1px solid {C_BORDER}; }}")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 10, 14, 12)
        bl.setSpacing(8)
        b_add = _pill("+ Hisse", primary=False)
        b_add.clicked.connect(self._add_stock)
        b_sec = _pill("Bölüm")
        b_sec.clicked.connect(self._add_separator)
        b_ref = _pill("↻", width=24)
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

        head, self.lbl_notes_status = self._title_row("Notlar")
        pnl.addWidget(head)

        list_wrap = QWidget()
        lw = QVBoxLayout(list_wrap)
        lw.setContentsMargins(10, 0, 10, 10)
        self.notes_list = QListWidget()
        self.notes_list.setFixedHeight(140)
        self.notes_list.setFont(_f(13))
        self.notes_list.setStyleSheet(
            f"QListWidget {{ background: {C_CARD}; border: none;"
            f" border-radius: {R_CARD}px; color: {C_TEXT2}; padding: 0; outline: none; }}"
            f"QListWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {C_HAIRLINE}; }}"
            f"QListWidget::item:selected {{ background: {C_BLUE}; color: #ffffff; }}"
        )
        self.notes_list.currentRowChanged.connect(self._note_selected)
        self.notes_list.itemDoubleClicked.connect(self._rename_note)
        lw.addWidget(self.notes_list)
        pnl.addWidget(list_wrap)

        ed_wrap = QWidget()
        ew = QVBoxLayout(ed_wrap)
        ew.setContentsMargins(10, 0, 10, 10)
        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Not içeriği…")
        self.notes_editor.setEnabled(False)
        self.notes_editor.setFont(_f(13))
        self.notes_editor.setStyleSheet(
            f"QTextEdit {{ background: {C_EDITOR_BG}; border: 1px solid {C_BORDER};"
            f" border-radius: {R_CARD}px; color: {C_TEXT2}; padding: 10px; }}"
            f"QTextEdit:focus {{ border-color: rgba(10,132,255,150); }}"
        )
        self.notes_editor.textChanged.connect(self._note_text_changed)
        ew.addWidget(self.notes_editor)
        pnl.addWidget(ed_wrap, 1)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 14, 12)
        bl.setSpacing(8)
        b_new = _pill("+ Not")
        b_new.clicked.connect(self._add_note)
        b_del = _pill("Sil")
        b_del.setStyleSheet(
            f"QPushButton {{ background: rgba(255,69,58,36); color: {C_RED}; border: none;"
            f" border-radius: {R_BTN}px; padding: 0 12px; }}"
            "QPushButton:hover { background: rgba(255,69,58,64); }"
        )
        b_del.clicked.connect(self._delete_note)
        b_ref = _pill("↻", width=24)
        b_ref.clicked.connect(self._notes_load)
        hint = QLabel("1,5 sn otomatik kayıt")
        hint.setFont(_f(11))
        hint.setStyleSheet(f"color: {C_TEXT4}; background: transparent;")
        bl.addWidget(b_new)
        bl.addWidget(b_del)
        bl.addWidget(hint)
        bl.addStretch()
        bl.addWidget(b_ref)
        pnl.addWidget(bar)
        return page

    def _build_twitter_page(self):
        page = QWidget()
        page.setStyleSheet(f"QWidget {{ background: {C_PANEL_BG}; }}")
        pnl = QVBoxLayout(page)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        head, self.lbl_twitter_status = self._title_row("𝕏  TTKOM")
        pnl.addWidget(head)

        self.twitter_scroll = QScrollArea()
        self.twitter_host = QWidget()
        self.twitter_host.setStyleSheet("background: transparent;")
        self.twitter_layout = QVBoxLayout(self.twitter_host)
        self.twitter_layout.setContentsMargins(10, 6, 10, 10)
        self.twitter_layout.setSpacing(8)
        self.twitter_layout.setAlignment(Qt.AlignTop)
        self.twitter_scroll.setWidget(self.twitter_host)
        self.twitter_scroll.setWidgetResizable(True)
        self.twitter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.twitter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.twitter_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,45);"
            " border-radius: 3px; min-height: 24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        pnl.addWidget(self.twitter_scroll, 1)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 14, 12)
        b_ref = _pill("↻ Yenile", width=70)
        b_ref.clicked.connect(self._twitter_load)
        bl.addStretch()
        bl.addWidget(b_ref)
        pnl.addWidget(bar)
        return page

    def _twitter_load(self):
        import urllib.request, urllib.parse, urllib.error
        self.lbl_twitter_status.setText("yükleniyor…")
        for i in reversed(range(self.twitter_layout.count())):
            w = self.twitter_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_config.env")
        token = ""
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("TWITTER_BEARER_TOKEN="):
                        token = line.split("=", 1)[1].strip()

        if not token:
            self.lbl_twitter_status.setText("token yok")
            return

        try:
            query = urllib.parse.quote("TTKOM lang:tr -is:retweet")
            url = (
                f"https://api.twitter.com/2/tweets/search/recent"
                f"?query={query}&max_results=10"
                f"&tweet.fields=created_at,author_id,text"
                f"&expansions=author_id&user.fields=username,name"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json as _json
                data = _json.loads(resp.read().decode())

            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            # Yeni tweet tespiti — ilk yüklemede sadece seed et, sonraki polling'de alert aç
            incoming_ids = {tw.get("id", "") for tw in tweets}
            if self._twitter_known_ids:
                new_ids = incoming_ids - self._twitter_known_ids
                if new_ids and self._mode != 3:
                    self._twitter_alert = True
            self._twitter_known_ids = incoming_ids
            if not tweets:
                lbl = QLabel("Tweet bulunamadı.")
                lbl.setFont(_f(12))
                lbl.setStyleSheet(f"color: {C_TEXT3}; background: transparent;")
                self.twitter_layout.addWidget(lbl)
                self.lbl_twitter_status.setText("0 tweet")
                return

            for tw in tweets:
                tweet_id = tw.get("id", "")
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

                card = QWidget()
                card.setCursor(Qt.PointingHandCursor)
                card.setStyleSheet(
                    f"QWidget {{ background: rgba(255,255,255,18); border-radius: {R_CARD}px; }}"
                    f"QWidget:hover {{ background: rgba(255,255,255,30); }}"
                )
                card.mousePressEvent = (lambda e, u=tweet_url: __import__('subprocess').Popen(['open', u]))
                cv = QVBoxLayout(card)
                cv.setContentsMargins(10, 8, 10, 8)
                cv.setSpacing(4)

                user = users.get(tw.get("author_id", ""), {})
                name = user.get("name", "")
                uname = user.get("username", "")
                ts = tw.get("created_at", "")[:16].replace("T", " ")

                top = QHBoxLayout()
                lbl_name = QLabel(f"@{uname}" if uname else name)
                lbl_name.setFont(_f(11, QFont.Medium))
                lbl_name.setStyleSheet(f"color: {C_BLUE}; background: transparent;")
                lbl_ts = QLabel(ts)
                lbl_ts.setFont(_f(10))
                lbl_ts.setStyleSheet(f"color: rgba(235,235,245,128); background: transparent;")
                top.addWidget(lbl_name)
                top.addStretch()
                top.addWidget(lbl_ts)
                cv.addLayout(top)

                lbl_text = QLabel(tw.get("text", ""))
                lbl_text.setFont(_f(12))
                lbl_text.setStyleSheet(f"color: #ffffff; background: transparent;")
                lbl_text.setWordWrap(True)
                lbl_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                cv.addWidget(lbl_text)

                self.twitter_layout.addWidget(card)

            self.lbl_twitter_status.setText(f"{len(tweets)} tweet")

        except urllib.error.HTTPError as e:
            self.lbl_twitter_status.setText(f"hata {e.code}")
            err = QLabel(f"API hatası: {e.code}\n{e.reason}")
            err.setFont(_f(12))
            err.setStyleSheet(f"color: {C_RED}; background: transparent;")
            err.setWordWrap(True)
            self.twitter_layout.addWidget(err)
        except Exception as e:
            self.lbl_twitter_status.setText("hata")
            err = QLabel(str(e))
            err.setFont(_f(12))
            err.setStyleSheet(f"color: {C_RED}; background: transparent;")
            err.setWordWrap(True)
            self.twitter_layout.addWidget(err)

    def _twitter_poll(self):
        """Arka planda sessizce kontrol et; yeni tweet varsa alert aç."""
        import urllib.request, urllib.parse, urllib.error, json as _json
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_config.env")
        token = ""
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("TWITTER_BEARER_TOKEN="):
                        token = line.split("=", 1)[1].strip()
        if not token:
            return
        try:
            query = urllib.parse.quote("TTKOM lang:tr -is:retweet")
            url = (
                f"https://api.twitter.com/2/tweets/search/recent"
                f"?query={query}&max_results=10"
                f"&tweet.fields=id"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
            incoming_ids = {tw.get("id", "") for tw in data.get("data", [])}
            if self._twitter_known_ids:
                new_ids = incoming_ids - self._twitter_known_ids
                if new_ids and self._mode != 3:
                    self._twitter_alert = True
                    self._twitter_known_ids = incoming_ids
            else:
                self._twitter_known_ids = incoming_ids
        except Exception:
            pass

    # ── Panel aç/kapat ──────────────────────────────────────────────────
    def _quit_menu(self, event):
        m = _menu(self)
        m.addAction("Uygulamayı Kapat", QApplication.instance().quit)
        m.exec(event.globalPosition().toPoint())

    def _toggle(self, mode):
        closing = (self._mode == mode)
        if closing:
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
                self._twitter_alert = False
                self._twitter_blink_state = False
            target_w = PANEL_W
        self._paint_tab(self.tab_stock, self._mode == 1)
        self._paint_tab(self.tab_notes, self._mode == 2)
        self._paint_tab(self.tab_twitter, self._mode == 3)
        self._anim.stop()
        self._anim.setStartValue(min(self.panel.maximumWidth(), PANEL_W))
        self._anim.setEndValue(target_w)
        self._anim.start()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowDeactivate and self._mode != 0:
            self._toggle(self._mode)
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and self._mode != 0:
            gp = event.globalPosition().toPoint()
            if not self.geometry().contains(gp):
                self._toggle(self._mode)
        return super().eventFilter(obj, event)

    def _install_global_mouse_monitor(self):
        try:
            from AppKit import NSEvent
            mask = (1 << 1) | (1 << 3)  # NSLeftMouseDown | NSRightMouseDown

            def handler(nsevent):
                if self._mode == 0:
                    return
                from AppKit import NSScreen
                loc = NSEvent.mouseLocation()
                sh = NSScreen.mainScreen().frame().size.height
                gx = int(loc.x)
                gy = int(sh - loc.y)
                from PySide6.QtCore import QPoint
                if not self.geometry().contains(QPoint(gx, gy)):
                    QTimer.singleShot(0, lambda m=self._mode: self._toggle(m) if self._mode != 0 else None)

            self._ns_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)
        except Exception as e:
            print("global mouse monitor hatası:", e)

    def _check_outside_click(self):
        if self._mode == 0:
            return
        try:
            from AppKit import NSEvent, NSScreen
            buttons = NSEvent.pressedMouseButtons()
            if not (buttons & 0b11):  # sol veya sağ buton basılı değil
                self._was_pressed = False
                return
            if getattr(self, '_was_pressed', False):
                return
            self._was_pressed = True
            loc = NSEvent.mouseLocation()
            sh = NSScreen.mainScreen().frame().size.height
            from PySide6.QtCore import QPoint
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
        self.rows.clear()
        self.headers.clear()
        self.lbl_empty.setParent(None)
        self._clear_layout(self.rows_layout)

        order = []
        groups = []           # [(sep_uid or None, [stock dicts])]
        current = (None, [])
        for s in self.stocks:
            sym = s["symbol"]
            if sym.startswith(_SEP_SYMBOL):
                groups.append(current)
                current = (sym, [])
            else:
                current[1].append(s)
        groups.append(current)

        for uid, items in groups:
            if uid is None and not items:
                continue
            section = QWidget()
            sv = QVBoxLayout(section)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(5)

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
            card.setStyleSheet(f"#card {{ background: {C_CARD}; border-radius: {R_CARD}px; }}")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)

            visible_rows = 0
            for i, s in enumerate(items):
                sym = s["symbol"]
                if self._filter and self._filter not in sym.upper():
                    continue
                if visible_rows > 0:
                    cv.addWidget(_hairline())
                row = StockRow(sym, s.get("entry"), s.get("exit"))
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
        q = text.strip().upper()
        self._filter = q
        known = any(s["symbol"].upper() == q for s in self.stocks)
        self.btn_add_inline.setVisible(len(q) >= 3 and not known)
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
    def _on_dropped(self, moved, target):
        idx = next((i for i, s in enumerate(self.stocks) if s["symbol"] == moved), None)
        if idx is None:
            return
        item = self.stocks.pop(idx)
        if target is None or target == moved:
            self.stocks.append(item)
        else:
            tgt = next((i for i, s in enumerate(self.stocks) if s["symbol"] == target), len(self.stocks))
            self.stocks.insert(tgt, item)
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
        counters = []
        for s in self.stocks:
            if s["symbol"].startswith(_SEP_SYMBOL):
                _, c = _parse_sep_symbol(s["symbol"])
                if c.isdigit():
                    counters.append(int(c))
        counter = (max(counters) + 1) if counters else 0
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
        fetch_all(symbols, lambda r: QApplication.instance().data_signal.emit(r))

    def apply_data(self, results):
        from datetime import datetime
        self._fetching = False
        self._last_data = {i["symbol"]: i for i in results}
        self.lbl_stock_status.setText(datetime.now().strftime("%H:%M"))
        self._apply_cached_prices()

    def _apply_cached_prices(self):
        for sym, item in getattr(self, "_last_data", {}).items():
            if sym in self.rows:
                self.rows[sym].update_data(item["price"], item["change_pct"])

    # ── Notlar ──────────────────────────────────────────────────────────
    def _notes_load(self):
        self.lbl_notes_status.setText("Yükleniyor…")
        fetch_notes(lambda notes: QApplication.instance().notes_signal.emit(notes if notes else []))

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
