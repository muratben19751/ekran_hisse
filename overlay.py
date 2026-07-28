import json
import os

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal, QSize
from PySide6.QtGui import QFont, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QInputDialog, QApplication, QSizePolicy, QMenu,
    QListWidget, QTextEdit, QLineEdit, QDialog, QScrollArea,
)

from data_fetcher import fetch_all
from notes_api_client import fetch_notes, save_notes

STOCKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocks.json")
REFRESH_INTERVAL_MS = 60_000

PANEL_W  = 285
TAB_W    = 32
ANIM_MS  = 200

BG_COLOR     = "rgba(18, 18, 22, 230)"
HEADER_COLOR = "#b0b8c8"
POS_COLOR    = "#4ade80"
NEG_COLOR    = "#f87171"
NEU_COLOR    = "#e2e8f0"
BTN_HOVER    = "rgba(255,255,255,40)"

TAB_STOCK_COLOR = "rgba(60, 120, 255, 220)"
TAB_NOTES_COLOR = "rgba(60, 180, 100, 220)"


def _main_screen():
    return QApplication.primaryScreen().geometry()


def _ask_text(title, label, default="", parent=None):
    """Panele bitişik, yeşil temalı, küçük input dialog."""
    sc = QApplication.primaryScreen().availableGeometry()
    dlg = QDialog(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    dlg.setAttribute(Qt.WA_TranslucentBackground)
    dlg.setStyleSheet(
        "QDialog { background: transparent; }"
    )

    container = QWidget(dlg)
    container.setObjectName("dlgbox")
    container.setStyleSheet(
        "#dlgbox {"
        "  background: rgba(22, 32, 22, 245);"
        "  border: 1px solid rgba(60,180,100,120);"
        "  border-radius: 8px;"
        "}"
    )

    vlay = QVBoxLayout(container)
    vlay.setContentsMargins(12, 10, 12, 10)
    vlay.setSpacing(8)

    lbl = QLabel(label)
    lbl.setFont(QFont("Arial", 10))
    lbl.setStyleSheet("color: rgba(60,180,100,220); background: transparent;")
    vlay.addWidget(lbl)

    inp = QLineEdit(default)
    inp.setFont(QFont("Menlo", 11))
    inp.setStyleSheet(
        "QLineEdit {"
        "  background: rgba(60,180,100,25);"
        "  border: 1px solid rgba(60,180,100,80);"
        "  border-radius: 4px;"
        "  color: #d4e8c2;"
        "  padding: 4px 8px;"
        "}"
        "QLineEdit:focus { border-color: rgba(60,180,100,180); }"
    )
    inp.selectAll()
    vlay.addWidget(inp)

    bar = QHBoxLayout()
    bar.setSpacing(6)

    def _btn(text, primary=False):
        b = QPushButton(text)
        b.setFont(QFont("Arial", 10))
        b.setFixedHeight(26)
        if primary:
            b.setStyleSheet(
                "QPushButton { background: rgba(60,180,100,180); color: white;"
                " border: none; border-radius: 4px; padding: 0 14px; }"
                "QPushButton:hover { background: rgba(60,180,100,220); }"
            )
        else:
            b.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,15); color: #888;"
                " border: none; border-radius: 4px; padding: 0 14px; }"
                "QPushButton:hover { background: rgba(255,255,255,30); color: #ccc; }"
            )
        return b

    ok_btn     = _btn("OK", primary=True)
    cancel_btn = _btn("İptal")
    bar.addStretch()
    bar.addWidget(cancel_btn)
    bar.addWidget(ok_btn)
    vlay.addLayout(bar)

    container.adjustSize()
    w = container.sizeHint().width() + 24
    h = container.sizeHint().height() + 20
    container.setGeometry(0, 0, w, h)
    dlg.resize(w, h)

    # Panele bitişik (solunda), dikey ortada
    x = sc.x() + sc.width() - TAB_W - PANEL_W - w
    y = sc.y() + (sc.height() - h) // 2
    dlg.move(x, y)

    result = [None]

    def _ok():
        result[0] = inp.text().strip()
        dlg.accept()

    def _cancel():
        dlg.reject()

    ok_btn.clicked.connect(_ok)
    cancel_btn.clicked.connect(_cancel)
    inp.returnPressed.connect(_ok)

    def _boost():
        try:
            import objc
            ns_view = objc.objc_object(c_void_p=int(dlg.winId()))
            ns_win = ns_view.window()
            ns_win.setLevel_(1002)
            ns_win.setHidesOnDeactivate_(False)
            ns_win.makeKeyAndOrderFront_(None)
        except Exception:
            pass

    QTimer.singleShot(0, _boost)
    dlg.exec()
    return result[0]


def load_stocks():
    if os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE) as f:
            data = json.load(f)
        # Eski format (sadece string listesi) → yeni formata çevir
        if data and isinstance(data[0], str):
            return [{"symbol": s, "entry": None, "exit": None} for s in data]
        return data
    return []


def save_stocks(stocks):
    with open(STOCKS_FILE, "w") as f:
        json.dump(stocks, f)


class PriceBar(QWidget):
    """Giriş ve çıkış fiyatı arasında kalın yatay çizgi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self._entry = None
        self._exit = None
        self._price = None

    def set_levels(self, entry, exit_price, current_price):
        self._entry = entry
        self._exit = exit_price
        self._price = current_price
        self.update()

    def paintEvent(self, event):
        if self._entry is None or self._exit is None:
            return
        lo = min(self._entry, self._exit)
        hi = max(self._entry, self._exit)
        if hi == lo:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin = 8

        def x_for(v):
            return margin + (v - lo) / (hi - lo) * (w - 2 * margin)

        x_entry = x_for(self._entry)
        x_exit  = x_for(self._exit)

        # Kalın yatay çizgi (giriş→çıkış arası)
        pen = QPen(QColor("#4ade80"), 4, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        mid_y = h // 2
        p.drawLine(int(min(x_entry, x_exit)), mid_y, int(max(x_entry, x_exit)), mid_y)

        # Giriş noktası (beyaz dikey çizgi)
        pen2 = QPen(QColor("#ffffff"), 2)
        p.setPen(pen2)
        p.drawLine(int(x_entry), 1, int(x_entry), h - 1)

        # Çıkış noktası (sarı dikey çizgi)
        pen3 = QPen(QColor("#facc15"), 2)
        p.setPen(pen3)
        p.drawLine(int(x_exit), 1, int(x_exit), h - 1)

        # Güncel fiyat (mavi üçgen/nokta)
        if self._price is not None and lo <= self._price <= hi:
            xp = x_for(self._price)
            pen4 = QPen(QColor("#60a5fa"), 2)
            p.setPen(pen4)
            p.drawLine(int(xp), 0, int(xp), h)

        p.end()


def _parse_price(val: str):
    """'1.234,56' veya '1234.56' veya '67,5' gibi girişleri float'a çevirir."""
    v = val.strip()
    if ',' in v and '.' in v:
        v = v.replace('.', '').replace(',', '.')
    else:
        v = v.replace(',', '.')
    return float(v)


_SEP_SYMBOL = "---"


def _parse_sep_symbol(symbol: str):
    """("Bank", "0") döner. Eski "---:0" ve yeni "---:Bank:0" formatlarını destekler."""
    parts = symbol.split(":", 2)
    if len(parts) == 3:
        return parts[1], parts[2]
    if len(parts) == 2:
        return "", parts[1]
    return "", "0"


class SeparatorRow(QWidget):
    remove_requested = Signal(str)
    move_requested   = Signal(str, int)
    rename_requested = Signal(str)
    collapse_toggled = Signal(str, bool)

    def __init__(self, uid, parent=None):
        super().__init__(parent)
        self.symbol = uid
        self._collapsed = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(30, 120, 50, 200); border-radius: 4px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(4)

        self._btn_collapse = QPushButton("▼")
        self._btn_collapse.setFixedSize(18, 18)
        self._btn_collapse.setCursor(Qt.PointingHandCursor)
        self._btn_collapse.setStyleSheet(
            "QPushButton { background: transparent; color: #668; border: none; font-size: 9px; }"
            "QPushButton:hover { color: #aaa; }"
        )
        self._btn_collapse.clicked.connect(self._toggle_collapse)

        self._lbl_name = QLabel()
        self._lbl_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._lbl_name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        name, _ = _parse_sep_symbol(uid)
        self._set_name_label(name)
        self._lbl_name.mouseDoubleClickEvent = lambda e: self.rename_requested.emit(self.symbol)

        btn_up = QPushButton("▲")
        btn_up.setFixedSize(18, 18)
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 9px; }"
            "QPushButton:hover { color: #aaa; }"
        )
        btn_up.clicked.connect(lambda: self.move_requested.emit(self.symbol, -1))

        btn_dn = QPushButton("▼")
        btn_dn.setFixedSize(18, 18)
        btn_dn.setCursor(Qt.PointingHandCursor)
        btn_dn.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 9px; }"
            "QPushButton:hover { color: #aaa; }"
        )
        btn_dn.clicked.connect(lambda: self.move_requested.emit(self.symbol, +1))

        btn_del = QPushButton("×")
        btn_del.setFixedSize(18, 18)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 13px; }"
            f"QPushButton:hover {{ color: {NEG_COLOR}; }}"
        )
        btn_del.clicked.connect(lambda: self.remove_requested.emit(self.symbol))

        layout.addWidget(self._btn_collapse)
        layout.addWidget(self._lbl_name, 1)
        layout.addWidget(btn_up)
        layout.addWidget(btn_dn)
        layout.addWidget(btn_del)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

    def _set_name_label(self, name: str):
        text = f"─ {name} " if name else "──────────"
        self._lbl_name.setText(text)
        self._lbl_name.setFont(QFont("Menlo", 8, QFont.Bold))
        self._lbl_name.setStyleSheet("color: #facc15; background: transparent;")

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._btn_collapse.setText("▶" if self._collapsed else "▼")
        self.collapse_toggled.emit(self.symbol, self._collapsed)

    def set_name(self, name: str):
        self._set_name_label(name)

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(28,28,36,240); color: #ccc;"
            " border: 1px solid rgba(255,255,255,20); border-radius: 6px; }"
            "QMenu::item { padding: 4px 16px; }"
            "QMenu::item:selected { background: rgba(255,255,255,25); }"
        )
        menu.addAction("Yeniden adlandır", lambda: self.rename_requested.emit(self.symbol))
        menu.exec(self.mapToGlobal(pos))


class StockRow(QWidget):
    remove_requested = Signal(str)
    levels_changed   = Signal(str, object, object)  # symbol, entry, exit
    move_requested   = Signal(str, int)              # symbol, direction (-1=yukarı, +1=aşağı)

    def __init__(self, symbol, entry=None, exit_price=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self._entry = entry
        self._exit  = exit_price
        self._price = None
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 3, 8, 2)
        outer.setSpacing(1)

        # Üst satır: sembol, fiyat, değişim, sil
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        self.lbl_symbol = QLabel(symbol)
        self.lbl_symbol.setFont(QFont("Menlo", 11, QFont.Bold))
        self.lbl_symbol.setStyleSheet(f"color: {NEU_COLOR};")
        self.lbl_symbol.setFixedWidth(70)

        self.lbl_price = QLabel("—")
        self.lbl_price.setFont(QFont("Menlo", 10))
        self.lbl_price.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_price.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lbl_change = QLabel("—")
        self.lbl_change.setFont(QFont("Menlo", 11, QFont.Bold))
        self.lbl_change.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_change.setFixedWidth(72)
        self.lbl_change.setStyleSheet(f"color: {HEADER_COLOR};")

        btn_del = QPushButton("×")
        btn_del.setFixedSize(18, 18)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 13px; }"
            f"QPushButton:hover {{ color: {NEG_COLOR}; }}"
        )
        btn_del.clicked.connect(lambda: self.remove_requested.emit(self.symbol))

        btn_up = QPushButton("▲")
        btn_up.setFixedSize(18, 18)
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 9px; }"
            "QPushButton:hover { color: #aaa; }"
        )
        btn_up.clicked.connect(lambda: self.move_requested.emit(self.symbol, -1))

        btn_dn = QPushButton("▼")
        btn_dn.setFixedSize(18, 18)
        btn_dn.setCursor(Qt.PointingHandCursor)
        btn_dn.setStyleSheet(
            "QPushButton { background: transparent; color: #778; border: none; font-size: 9px; }"
            "QPushButton:hover { color: #aaa; }"
        )
        btn_dn.clicked.connect(lambda: self.move_requested.emit(self.symbol, +1))

        top.addWidget(self.lbl_symbol)
        top.addWidget(self.lbl_price)
        top.addWidget(self.lbl_change)
        top.addWidget(btn_up)
        top.addWidget(btn_dn)
        top.addWidget(btn_del)
        outer.addLayout(top)

        # Alt satır: giriş/çıkış bar + etiketler
        self.bar_widget = PriceBar()
        self.bar_widget.setVisible(entry is not None or exit_price is not None)
        outer.addWidget(self.bar_widget)

        # Giriş/çıkış etiket satırı
        self.lbl_levels = QLabel()
        self.lbl_levels.setFont(QFont("Menlo", 8))
        self.lbl_levels.setStyleSheet("color: #8899aa; background: transparent;")
        self.lbl_levels.setAlignment(Qt.AlignLeft)
        self._update_levels_label()
        outer.addWidget(self.lbl_levels)

        self.bar_widget.set_levels(entry, exit_price, None)

        # Sağ tık → giriş/çıkış ayarla
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

    def _update_levels_label(self):
        e = f"G:{self._entry:.2f}" if self._entry is not None else "G:—"
        x = f"Ç:{self._exit:.2f}"  if self._exit  is not None else "Ç:—"
        if self._entry is not None and self._price is not None and self._entry != 0:
            pnl_pct = (self._price - self._entry) / self._entry * 100
            sign = "+" if pnl_pct >= 0 else ""
            color = POS_COLOR if pnl_pct >= 0 else NEG_COLOR
            pnl_str = f'  <span style="color:{color}">({sign}{pnl_pct:.1f}%)</span>'
        else:
            pnl_str = ""
        self.lbl_levels.setText(f"  {e}  {x}{pnl_str}")
        self.lbl_levels.setTextFormat(Qt.RichText)
        has = self._entry is not None or self._exit is not None
        self.bar_widget.setVisible(has)
        self.lbl_levels.setVisible(has)

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(28,28,36,240); color: #ccc;"
            " border: 1px solid rgba(255,255,255,20); border-radius: 6px; }"
            "QMenu::item { padding: 4px 16px; }"
            "QMenu::item:selected { background: rgba(255,255,255,25); }"
        )
        menu.addAction("Giriş fiyatı ayarla",  self._set_entry)
        menu.addAction("Çıkış fiyatı ayarla",  self._set_exit)
        menu.addAction("Giriş/Çıkış temizle",  self._clear_levels)
        menu.exec(self.mapToGlobal(pos))

    def _set_entry(self):
        val = _ask_text("Giriş Fiyatı", f"{self.symbol} giriş fiyatı:",
                        default=str(self._entry) if self._entry else "")
        if val is None:
            return
        try:
            self._entry = _parse_price(val)
        except ValueError:
            return
        self._update_levels_label()
        self.bar_widget.set_levels(self._entry, self._exit, self._price)
        self.levels_changed.emit(self.symbol, self._entry, self._exit)

    def _set_exit(self):
        val = _ask_text("Çıkış Fiyatı", f"{self.symbol} çıkış fiyatı:",
                        default=str(self._exit) if self._exit else "")
        if val is None:
            return
        try:
            self._exit = _parse_price(val)
        except ValueError:
            return
        self._update_levels_label()
        self.bar_widget.set_levels(self._entry, self._exit, self._price)
        self.levels_changed.emit(self.symbol, self._entry, self._exit)

    def _clear_levels(self):
        self._entry = None
        self._exit  = None
        self._update_levels_label()
        self.bar_widget.set_levels(None, None, self._price)
        self.levels_changed.emit(self.symbol, None, None)

    def update_data(self, price, change_pct):
        self._price = price
        if price is None:
            self.lbl_price.setText("—")
            self.lbl_change.setText("—")
            self.lbl_change.setStyleSheet(f"color: {HEADER_COLOR};")
            return
        self.lbl_price.setText(f"₺{price:,.2f}")
        self.bar_widget.set_levels(self._entry, self._exit, price)
        self._update_levels_label()
        if change_pct is None:
            self.lbl_change.setText("—")
            self.lbl_change.setStyleSheet(f"color: {HEADER_COLOR};")
        elif change_pct > 0:
            self.lbl_change.setText(f"+{change_pct:.2f}%")
            self.lbl_change.setStyleSheet(f"color: {POS_COLOR};")
        elif change_pct < 0:
            self.lbl_change.setText(f"{change_pct:.2f}%")
            self.lbl_change.setStyleSheet(f"color: {NEG_COLOR};")
        else:
            self.lbl_change.setText("0.00%")
            self.lbl_change.setStyleSheet(f"color: {NEU_COLOR};")


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._mode = 0       # 0=kapalı, 1=hisse, 2=notlar
        self._fetching = False
        self.stocks = load_stocks()   # [{symbol, entry, exit}]
        self.rows = {}
        self._collapsed_sections = {}  # {sep_symbol: bool}

        # Notlar state
        self._notes = []
        self._current_note = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._notes_save_now)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._build_ui()

        sc = _main_screen()
        sc_avail = QApplication.primaryScreen().availableGeometry()
        win_h = sc_avail.height() // 2
        win_y = sc_avail.y() + sc_avail.height() - win_h  # alttan ortaya
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

        # Hisse timer
        self.stock_timer = QTimer(self)
        self.stock_timer.timeout.connect(self._stocks_refresh)
        self.stock_timer.start(REFRESH_INTERVAL_MS)
        if self.stocks:
            self._stocks_refresh()

        # Notları başlangıçta arka planda yükle
        QTimer.singleShot(1000, self._notes_load)

    # ── UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sekme sütunu
        tab_col = QWidget()
        tab_col.setFixedWidth(TAB_W)
        tc_lyt = QVBoxLayout(tab_col)
        tc_lyt.setContentsMargins(0, 0, 0, 0)
        tc_lyt.setSpacing(4)

        self.tab_stock = self._make_tab("◀", TAB_STOCK_COLOR)
        self.tab_stock.mousePressEvent = self._stock_tab_press

        self.tab_notes = self._make_tab("N", TAB_NOTES_COLOR)
        self.tab_notes.mousePressEvent = self._notes_tab_press

        tc_lyt.addStretch()
        tc_lyt.addWidget(self.tab_stock)
        tc_lyt.addWidget(self.tab_notes)

        # Panel (animasyon hedefi — maximumWidth)
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet(
            "#panel {"
            f"  background: {BG_COLOR};"
            "  border-top-left-radius: 8px;"
            "  border-bottom-left-radius: 8px;"
            "  border: 1px solid rgba(255,255,255,14);"
            "  border-right: none;"
            "}"
        )
        self.panel.setMinimumWidth(0)
        self.panel.setMaximumWidth(PANEL_W)

        pnl = QVBoxLayout(self.panel)
        pnl.setContentsMargins(0, 0, 0, 0)
        pnl.setSpacing(0)

        # Hisse içeriği
        self.stocks_page = self._build_stocks_page()
        pnl.addWidget(self.stocks_page)

        # Notlar içeriği
        self.notes_page = self._build_notes_page()
        self.notes_page.setVisible(False)
        pnl.addWidget(self.notes_page)

        root.addWidget(self.panel)
        root.addWidget(tab_col)

    def _make_tab(self, label, color):
        tab = QWidget()
        tab.setFixedWidth(TAB_W)
        tab.setMinimumHeight(44)
        tab.setCursor(Qt.PointingHandCursor)
        oid = f"t{id(tab)}"
        tab.setObjectName(oid)
        tab.setStyleSheet(
            f"#{oid} {{"
            f"  background: {color};"
            "  border-top-left-radius: 8px;"
            "  border-bottom-left-radius: 8px;"
            "}"
        )
        lyt = QVBoxLayout(tab)
        lyt.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFont(QFont("Arial", 11, QFont.Bold))
        lbl.setStyleSheet("color: white; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        lyt.addWidget(lbl)
        tab._label = lbl
        return tab

    def _btn(self, text, slot):
        b = QPushButton(text)
        b.setFixedSize(26, 20)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(QFont("Arial", 11))
        b.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,15); color: #aaa; border: none; border-radius: 3px; }"
            f"QPushButton:hover {{ background: {BTN_HOVER}; color: white; }}"
        )
        b.clicked.connect(slot)
        return b

    # ── Hisse Sayfası ────────────────────────────────────────────────────
    def _build_stocks_page(self):
        w = QWidget()
        pnl = QVBoxLayout(w)
        pnl.setContentsMargins(0, 8, 0, 8)
        pnl.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(10, 2, 10, 6)
        lbl_title = QLabel("BIST Hisse")
        lbl_title.setFont(QFont("Arial", 10))
        lbl_title.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_stock_status = QLabel("")
        self.lbl_stock_status.setFont(QFont("Arial", 9))
        self.lbl_stock_status.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_stock_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.lbl_stock_status)
        pnl.addLayout(hdr)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.rows_layout.setAlignment(Qt.AlignTop)

        rows_container = QWidget()
        rows_container.setLayout(self.rows_layout)
        rows_container.setStyleSheet("background: transparent;")

        scroll = QScrollArea()
        scroll.setWidget(rows_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: rgba(255,255,255,10); width: 5px; border-radius: 2px; }"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,40); border-radius: 2px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        pnl.addWidget(scroll, 1)

        self.lbl_empty = QLabel("+ ile hisse ekleyin")
        self.lbl_empty.setFont(QFont("Arial", 10))
        self.lbl_empty.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setContentsMargins(10, 10, 10, 10)
        self.rows_layout.addWidget(self.lbl_empty)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 2)
        bar.setSpacing(4)
        bar.addWidget(self._btn("+", self._add_stock))
        bar.addWidget(self._btn("─", self._add_separator))
        bar.addWidget(self._btn("↺", self._stocks_refresh))
        bar.addStretch()
        bar.addWidget(self._btn("✕", lambda: self._toggle(1)))
        pnl.addLayout(bar)

        self._rebuild_rows()
        return w

    # ── Notlar Sayfası ───────────────────────────────────────────────────
    def _build_notes_page(self):
        w = QWidget()
        pnl = QVBoxLayout(w)
        pnl.setContentsMargins(0, 8, 0, 8)
        pnl.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(10, 2, 10, 6)
        lbl_title = QLabel("Notlar")
        lbl_title.setFont(QFont("Arial", 10))
        lbl_title.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_notes_status = QLabel("")
        self.lbl_notes_status.setFont(QFont("Arial", 9))
        self.lbl_notes_status.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_notes_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.lbl_notes_status)
        pnl.addLayout(hdr)

        self.notes_list = QListWidget()
        self.notes_list.setFixedHeight(120)
        self.notes_list.setStyleSheet(
            "QListWidget { background: rgba(255,255,255,5); border: none; color: #ccc; font-size: 11px; }"
            "QListWidget::item { padding: 4px 8px; border-bottom: 1px solid rgba(255,255,255,8); }"
            "QListWidget::item:selected { background: rgba(60,180,100,60); color: white; }"
        )
        self.notes_list.currentRowChanged.connect(self._note_selected)
        self.notes_list.itemDoubleClicked.connect(self._rename_note)
        pnl.addWidget(self.notes_list)

        self.notes_editor = QTextEdit()
        self.notes_editor.setPlaceholderText("Not içeriği…")
        self.notes_editor.setEnabled(False)
        self.notes_editor.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(30, 35, 25, 220);"
            "  border: none;"
            "  border-top: 1px solid rgba(60,180,100,40);"
            "  color: #d4e8c2;"
            "  font-family: Menlo, monospace;"
            "  font-size: 11px;"
            "  padding: 6px 8px;"
            "}"
        )
        self.notes_editor.textChanged.connect(self._note_text_changed)
        pnl.addWidget(self.notes_editor, 1)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 2)
        bar.setSpacing(4)
        bar.addWidget(self._btn("+", self._add_note))
        bar.addWidget(self._btn("×", self._delete_note))
        bar.addWidget(self._btn("↺", self._notes_load))
        bar.addStretch()
        bar.addWidget(self._btn("✕", lambda: self._toggle(2)))
        pnl.addLayout(bar)

        return w

    # ── Sekme Olayları ───────────────────────────────────────────────────
    def _stock_tab_press(self, event):
        if event.button() == Qt.RightButton:
            self._quit_menu(event)
        else:
            self._toggle(1)

    def _notes_tab_press(self, event):
        if event.button() == Qt.RightButton:
            self._quit_menu(event)
        else:
            self._toggle(2)

    def _quit_menu(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(28,28,36,240); color: #ccc;"
            " border: 1px solid rgba(255,255,255,20); border-radius: 6px; }"
            "QMenu::item:selected { background: rgba(255,255,255,25); }"
        )
        menu.addAction("Uygulamayı Kapat", QApplication.instance().quit)
        menu.exec(event.globalPosition().toPoint())

    # ── Panel Aç/Kapat ───────────────────────────────────────────────────
    def _toggle(self, mode):
        closing = (self._mode == mode)

        if closing:
            self._mode = 0
            self.tab_stock._label.setText("◀")
            self.tab_notes._label.setText("N")
            target_w = 0
        else:
            prev_mode = self._mode
            self._mode = mode

            self.stocks_page.setVisible(mode == 1)
            self.notes_page.setVisible(mode == 2)

            if mode == 1:
                self.tab_stock._label.setText("▶")
                self.tab_notes._label.setText("N")
                if prev_mode == 0:
                    self._stocks_refresh()
            else:
                self.tab_stock._label.setText("◀")
                self.tab_notes._label.setText("▶")
                if prev_mode == 0:
                    self._notes_load()

            target_w = PANEL_W

        self._anim.stop()
        self._anim.setStartValue(self.panel.maximumWidth() if self.panel.maximumWidth() < 9999 else PANEL_W)
        self._anim.setEndValue(target_w)
        self._anim.start()

    # ── Hisse İşlemleri ──────────────────────────────────────────────────
    def _rebuild_rows(self):
        for row in list(self.rows.values()):
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows.clear()
        current_sep = None
        for s in self.stocks:
            sym = s["symbol"]
            if sym.startswith(_SEP_SYMBOL):
                row = SeparatorRow(sym)
                is_collapsed = self._collapsed_sections.get(sym, False)
                row._collapsed = is_collapsed
                row._btn_collapse.setText("▶" if is_collapsed else "▼")
                row.remove_requested.connect(self._remove_stock)
                row.move_requested.connect(self._move_stock)
                row.rename_requested.connect(self._rename_separator)
                row.collapse_toggled.connect(self._on_collapse_toggled)
                current_sep = sym
            else:
                row = StockRow(sym, entry=s.get("entry"), exit_price=s.get("exit"))
                row.remove_requested.connect(self._remove_stock)
                row.levels_changed.connect(self._update_levels)
                row.move_requested.connect(self._move_stock)
                if current_sep is not None:
                    row.setVisible(not self._collapsed_sections.get(current_sep, False))
            self.rows_layout.addWidget(row)
            self.rows[sym] = row
        self.lbl_empty.setVisible(len(self.stocks) == 0)

    def _add_separator(self):
        name = _ask_text("Yeni Bölüm", "Bölüm adı (boş bırakılabilir):", default="", parent=self)
        if name is None:
            return
        existing = [s["symbol"] for s in self.stocks if s["symbol"].startswith(_SEP_SYMBOL)]
        counters = []
        for sym in existing:
            _, c = _parse_sep_symbol(sym)
            if c.isdigit():
                counters.append(int(c))
        counter = (max(counters) + 1) if counters else 0
        uid = f"{_SEP_SYMBOL}:{name}:{counter}"
        self.stocks.append({"symbol": uid, "entry": None, "exit": None})
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _move_stock(self, symbol, direction):
        idx = next((i for i, s in enumerate(self.stocks) if s["symbol"] == symbol), None)
        if idx is None:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.stocks):
            return
        self.stocks[idx], self.stocks[new_idx] = self.stocks[new_idx], self.stocks[idx]
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _on_collapse_toggled(self, symbol, is_collapsed):
        self._collapsed_sections[symbol] = is_collapsed
        inside = False
        for s in self.stocks:
            sym = s["symbol"]
            if sym == symbol:
                inside = True
                continue
            if inside:
                if sym.startswith(_SEP_SYMBOL):
                    break
                if sym in self.rows:
                    self.rows[sym].setVisible(not is_collapsed)

    def _rename_separator(self, symbol):
        current_name, counter = _parse_sep_symbol(symbol)
        new_name = _ask_text("Bölümü Yeniden Adlandır", "Yeni bölüm adı:",
                             default=current_name, parent=self)
        if new_name is None:
            return
        new_symbol = f"{_SEP_SYMBOL}:{new_name}:{counter}"
        for s in self.stocks:
            if s["symbol"] == symbol:
                s["symbol"] = new_symbol
                break
        if symbol in self._collapsed_sections:
            self._collapsed_sections[new_symbol] = self._collapsed_sections.pop(symbol)
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _add_stock(self):
        sym = _ask_text("Hisse Ekle", "BIST sembolü (örn: THYAO):", parent=self)
        if not sym:
            return
        sym = sym.upper()
        if any(s["symbol"] == sym for s in self.stocks):
            return
        self.stocks.append({"symbol": sym, "entry": None, "exit": None})
        save_stocks(self.stocks)
        self._rebuild_rows()
        self._stocks_refresh()

    def _remove_stock(self, symbol):
        self.stocks = [s for s in self.stocks if s["symbol"] != symbol]
        save_stocks(self.stocks)
        self._rebuild_rows()

    def _update_levels(self, symbol, entry, exit_price):
        for s in self.stocks:
            if s["symbol"] == symbol:
                s["entry"] = entry
                s["exit"]  = exit_price
                break
        save_stocks(self.stocks)

    def _stocks_refresh(self):
        symbols = [s["symbol"] for s in self.stocks if not s["symbol"].startswith(_SEP_SYMBOL)]
        if not symbols or self._fetching:
            return
        self._fetching = True
        self.lbl_stock_status.setText("güncelleniyor…")
        fetch_all(symbols, lambda r: QApplication.instance().data_signal.emit(r))

    def apply_data(self, results):
        from datetime import datetime
        self._fetching = False
        self.lbl_stock_status.setText(datetime.now().strftime("%H:%M"))
        for item in results:
            sym = item["symbol"]
            if sym in self.rows:
                self.rows[sym].update_data(item["price"], item["change_pct"])

    # ── Notlar İşlemleri ─────────────────────────────────────────────────
    def _notes_load(self):
        self.lbl_notes_status.setText("yükleniyor…")
        fetch_notes(lambda notes: QApplication.instance().notes_signal.emit(notes if notes else []))

    def _notes_loaded(self, notes):
        self._notes = notes if notes else []
        self._refresh_notes_list()
        self.lbl_notes_status.setText("")

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
        self._save_timer.start(1500)

    def _notes_save_now(self):
        self.lbl_notes_status.setText("kaydediliyor…")
        def _done(_):
            QTimer.singleShot(0, lambda: self.lbl_notes_status.setText(""))
        save_notes(self._notes, _done)

    def _rename_note(self, item):
        row = self.notes_list.row(item)
        if row < 0 or row >= len(self._notes):
            return
        new_title = _ask_text("Not Adını Değiştir", "Yeni ad:", default=self._notes[row]["title"], parent=self)
        if not new_title:
            return
        self._notes[row]["title"] = new_title
        self._refresh_notes_list()
        self._notes_save_now()

    def _add_note(self):
        title = _ask_text("Yeni Not", "Not başlığı:", parent=self)
        if not title:
            return
        self._notes.append({"title": title, "body": ""})
        self._current_note = len(self._notes) - 1
        self._refresh_notes_list()
        self._notes_save_now()

    def apply_notes(self, notes):
        if notes is None:
            self.lbl_notes_status.setText("bağlantı hatası")
            return
        self._notes_loaded(notes)

    def _delete_note(self):
        if self._current_note is None:
            return
        self._notes.pop(self._current_note)
        self._current_note = None
        self._refresh_notes_list()
        self._notes_save_now()
