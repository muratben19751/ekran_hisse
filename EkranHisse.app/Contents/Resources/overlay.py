import json
import os

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QInputDialog, QApplication, QSizePolicy, QMenu,
    QStackedWidget,
)

from data_fetcher import fetch_all
from notes_panel import NotesPanel

STOCKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocks.json")
REFRESH_INTERVAL_MS = 60_000

STOCKS_PANEL_W = 285
NOTES_PANEL_W  = 320
TAB_W          = 32
ANIM_MS        = 200

BG_COLOR     = "rgba(18, 18, 22, 230)"
HEADER_COLOR = "#666666"
POS_COLOR    = "#4ade80"
NEG_COLOR    = "#f87171"
NEU_COLOR    = "#e2e8f0"
BTN_HOVER    = "rgba(255,255,255,40)"

TAB_STOCK_COLOR = "rgba(60, 120, 255, 220)"   # mavi — hisse
TAB_NOTES_COLOR = "rgba(60, 180, 100, 220)"   # yeşil — notlar


def _main_screen():
    screens = QApplication.screens()
    if not screens:
        return QApplication.primaryScreen().availableGeometry()
    primary = min(screens, key=lambda s: s.geometry().x())
    return primary.availableGeometry()


def load_stocks():
    if os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE) as f:
            return json.load(f)
    return []


def save_stocks(symbols):
    with open(STOCKS_FILE, "w") as f:
        json.dump(symbols, f)


class StockRow(QWidget):
    remove_requested = Signal(str)

    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(4)

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
            "QPushButton { background: transparent; color: #444; border: none; font-size: 13px; }"
            f"QPushButton:hover {{ color: {NEG_COLOR}; }}"
        )
        btn_del.clicked.connect(lambda: self.remove_requested.emit(self.symbol))

        layout.addWidget(self.lbl_symbol)
        layout.addWidget(self.lbl_price)
        layout.addWidget(self.lbl_change)
        layout.addWidget(btn_del)

    def update_data(self, price, change_pct):
        if price is None:
            self.lbl_price.setText("—")
            self.lbl_change.setText("—")
            self.lbl_change.setStyleSheet(f"color: {HEADER_COLOR};")
            return
        self.lbl_price.setText(f"₺{price:,.2f}")
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


class StockWidget(QWidget):
    """Hisse panelinin içeriği (BIST listesi)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fetching = False
        self.symbols = load_stocks()
        self.rows = {}

        self.setObjectName("stockwidget")
        self.setStyleSheet(
            "#stockwidget {"
            f"  background: {BG_COLOR};"
            "  border-top-right-radius: 8px;"
            "  border-bottom-right-radius: 8px;"
            "  border: 1px solid rgba(255,255,255,14);"
            "  border-left: none;"
            "}"
        )
        self.setFixedWidth(STOCKS_PANEL_W)

        pnl = QVBoxLayout(self)
        pnl.setContentsMargins(0, 8, 0, 8)
        pnl.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(10, 2, 10, 6)
        lbl_title = QLabel("BIST Hisse")
        lbl_title.setFont(QFont("Arial", 10))
        lbl_title.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_status = QLabel("")
        self.lbl_status.setFont(QFont("Arial", 9))
        self.lbl_status.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.lbl_status)
        pnl.addLayout(hdr)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        pnl.addLayout(self.rows_layout)

        self.lbl_empty = QLabel("+ ile hisse ekleyin")
        self.lbl_empty.setFont(QFont("Arial", 10))
        self.lbl_empty.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setContentsMargins(10, 10, 10, 10)
        pnl.addWidget(self.lbl_empty)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 2)
        bar.setSpacing(4)
        bar.addWidget(self._btn("+", self._add_stock))
        bar.addWidget(self._btn("↺", self.refresh))
        bar.addStretch()
        pnl.addLayout(bar)

        self._rebuild_rows()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_INTERVAL_MS)
        if self.symbols:
            self.refresh()

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

    def _rebuild_rows(self):
        for row in list(self.rows.values()):
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows.clear()
        for sym in self.symbols:
            row = StockRow(sym)
            row.remove_requested.connect(self._remove_stock)
            self.rows_layout.addWidget(row)
            self.rows[sym] = row
        self.lbl_empty.setVisible(len(self.symbols) == 0)

    def _add_stock(self):
        text, ok = QInputDialog.getText(self, "Hisse Ekle", "BIST sembolü (örn: THYAO):")
        if not ok or not text.strip():
            return
        sym = text.strip().upper()
        if sym in self.symbols:
            return
        self.symbols.append(sym)
        save_stocks(self.symbols)
        self._rebuild_rows()
        self.refresh()

    def _remove_stock(self, symbol):
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            save_stocks(self.symbols)
            self._rebuild_rows()

    def refresh(self):
        if not self.symbols or self._fetching:
            return
        self._fetching = True
        self.lbl_status.setText("güncelleniyor…")
        fetch_all(self.symbols, lambda r: QApplication.instance().data_signal.emit(r))

    def apply_data(self, results):
        self._fetching = False
        self.lbl_status.setText("")
        for item in results:
            sym = item["symbol"]
            if sym in self.rows:
                self.rows[sym].update_data(item["price"], item["change_pct"])


class OverlayWindow(QWidget):
    # 0 = kapalı, 1 = hisse, 2 = notlar
    def __init__(self):
        super().__init__()
        self._mode = 0   # 0=kapalı, 1=hisse, 2=notlar

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._build_ui()
        self._reposition()

        # Panel animasyonu (maximumWidth üzerinden)
        self._anim = QPropertyAnimation(self.stack, b"maximumWidth")
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.stack.setMaximumWidth(0)

    # ── Konum ──────────────────────────────────────────────────────────
    def _reposition(self):
        sc = _main_screen()
        self.adjustSize()
        x = sc.x() + sc.width() - TAB_W
        y = sc.y() + (sc.height() - self.height()) // 2
        self.move(x, y)

    # ── UI İnşası ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sekme sütunu (iki sekme üst üste) ─────────────────────────
        self.tab_col = QWidget()
        self.tab_col.setFixedWidth(TAB_W)
        tab_col_layout = QVBoxLayout(self.tab_col)
        tab_col_layout.setContentsMargins(0, 0, 0, 0)
        tab_col_layout.setSpacing(4)

        # Hisse sekmesi (mavi, ◀ ok)
        self.tab_stock = self._make_tab("◀", TAB_STOCK_COLOR, top=True)
        self.tab_stock.mousePressEvent = self._stock_tab_press

        # Notlar sekmesi (yeşil, N)
        self.tab_notes = self._make_tab("N", TAB_NOTES_COLOR, top=False)
        self.tab_notes.mousePressEvent = self._notes_tab_press

        tab_col_layout.addWidget(self.tab_stock)
        tab_col_layout.addWidget(self.tab_notes)
        tab_col_layout.addStretch()

        # ── İçerik yığını ─────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setMaximumWidth(0)   # başlangıçta gizli

        self.stock_widget = StockWidget()
        self.notes_widget = NotesPanel()

        self.stack.addWidget(self.stock_widget)   # index 0
        self.stack.addWidget(self.notes_widget)   # index 1

        root.addWidget(self.tab_col)
        root.addWidget(self.stack)

    def _make_tab(self, label, color, top):
        tab = QWidget()
        tab.setFixedWidth(TAB_W)
        tab.setMinimumHeight(44)
        tab.setCursor(Qt.PointingHandCursor)
        radius = (
            "border-top-left-radius: 8px; border-bottom-left-radius: 8px;"
            if top else
            "border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
        )
        tab.setObjectName(f"tab_{label}")
        tab.setStyleSheet(
            f"QWidget#{tab.objectName()} {{"
            f"  background: {color};"
            f"  {radius}"
            "  border: 1px solid rgba(255,255,255,30);"
            "  border-right: none;"
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

    # ── Sekme olayları ─────────────────────────────────────────────────
    def _stock_tab_press(self, event):
        if event.button() == Qt.RightButton:
            self._show_quit_menu(event)
        else:
            self._open_panel(1)

    def _notes_tab_press(self, event):
        if event.button() == Qt.RightButton:
            self._show_quit_menu(event)
        else:
            self._open_panel(2)

    def _show_quit_menu(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(28,28,36,240); color: #ccc;"
            " border: 1px solid rgba(255,255,255,20); border-radius: 6px; }"
            "QMenu::item:selected { background: rgba(255,255,255,25); }"
        )
        menu.addAction("Uygulamayı Kapat", QApplication.instance().quit)
        menu.exec(event.globalPosition().toPoint())

    # ── Panel açma/kapama ──────────────────────────────────────────────
    def _open_panel(self, mode):
        sc = _main_screen()

        if self._mode == mode:
            # Aynı sekmeye basıldı → kapat
            self._mode = 0
            self.tab_stock._label.setText("◀")
            target_w = 0
            target_x = sc.x() + sc.width() - TAB_W
        else:
            # Farklı sekme veya kapalıyken açıyoruz
            self._mode = mode
            if mode == 1:
                self.stack.setCurrentIndex(0)
                panel_w = STOCKS_PANEL_W
                self.tab_stock._label.setText("▶")
                self.tab_notes._label.setText("N")
            else:
                self.stack.setCurrentIndex(1)
                panel_w = NOTES_PANEL_W
                self.tab_stock._label.setText("◀")
                self.tab_notes._label.setText("◀")

            target_w = panel_w
            target_x = sc.x() + sc.width() - TAB_W - panel_w

        self.move(target_x, self.y())

        self._anim.stop()
        self._anim.setStartValue(self.stack.width())
        self._anim.setEndValue(target_w)
        self._anim.start()

    # ── Veri ──────────────────────────────────────────────────────────
    def apply_data(self, results):
        self.stock_widget.apply_data(results)
