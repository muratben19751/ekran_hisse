from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QApplication, QSplitter, QInputDialog, QSizePolicy,
)
from notes_api_client import fetch_notes, save_notes

PANEL_W  = 320
TAB_W    = 32

BG_COLOR     = "rgba(18, 22, 18, 230)"
HEADER_COLOR = "#666666"
NEU_COLOR    = "#e2e8f0"
BTN_HOVER    = "rgba(255,255,255,40)"
TAB_COLOR    = "rgba(60, 180, 100, 220)"   # yeşil-mavi ton


class NotesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes = []       # [{"title": str, "body": str}]
        self._current = None   # seçili not indeksi
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_now)

        self.setObjectName("notespanel")
        self.setStyleSheet(
            "#notespanel {"
            f"  background: {BG_COLOR};"
            "  border-top-right-radius: 8px;"
            "  border-bottom-right-radius: 8px;"
            "  border: 1px solid rgba(255,255,255,14);"
            "  border-left: none;"
            "}"
        )
        self.setFixedWidth(PANEL_W)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        # ── Başlık ──────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(10, 2, 10, 6)
        lbl = QLabel("Notlar")
        lbl.setFont(QFont("Arial", 10))
        lbl.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_status = QLabel("")
        self.lbl_status.setFont(QFont("Arial", 9))
        self.lbl_status.setStyleSheet(f"color: {HEADER_COLOR};")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(self.lbl_status)
        layout.addLayout(hdr)

        # ── Not listesi ─────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setFixedHeight(130)
        self.list_widget.setStyleSheet(
            "QListWidget { background: rgba(255,255,255,5); border: none; color: #ccc; font-size: 11px; }"
            "QListWidget::item { padding: 4px 8px; border-bottom: 1px solid rgba(255,255,255,8); }"
            "QListWidget::item:selected { background: rgba(60,180,100,60); color: white; }"
            "QListWidget::item:hover { background: rgba(255,255,255,10); }"
        )
        self.list_widget.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.list_widget)

        # ── Metin editörü ───────────────────────────────────
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Not içeriğini buraya yaz…")
        self.editor.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(255,255,255,5);"
            "  border: none;"
            "  border-top: 1px solid rgba(255,255,255,10);"
            "  color: #e2e8f0;"
            "  font-family: Menlo, monospace;"
            "  font-size: 11px;"
            "  padding: 6px 8px;"
            "}"
        )
        self.editor.setEnabled(False)
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor, 1)

        # ── Buton çubuğu ─────────────────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 2)
        bar.setSpacing(4)
        bar.addWidget(self._btn("+", self._add_note))
        bar.addWidget(self._btn("×", self._delete_note))
        bar.addWidget(self._btn("↺", self._load))
        bar.addStretch()
        layout.addLayout(bar)

        self._load()

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

    def _load(self):
        self.lbl_status.setText("yükleniyor…")
        fetch_notes(self._on_loaded)

    def _on_loaded(self, notes):
        self._notes = notes if notes else []
        self._refresh_list()
        self.lbl_status.setText("")

    def _refresh_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for n in self._notes:
            self.list_widget.addItem(n.get("title", "—"))
        self.list_widget.blockSignals(False)
        if self._current is not None and self._current < len(self._notes):
            self.list_widget.setCurrentRow(self._current)
        else:
            self._current = None
            self.editor.setEnabled(False)
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)

    def _on_select(self, row):
        if row < 0 or row >= len(self._notes):
            return
        self._current = row
        self.editor.setEnabled(True)
        self.editor.blockSignals(True)
        self.editor.setPlainText(self._notes[row].get("body", ""))
        self.editor.blockSignals(False)

    def _on_text_changed(self):
        if self._current is None:
            return
        self._notes[self._current]["body"] = self.editor.toPlainText()
        self._save_timer.start(1500)   # 1.5s bekle, sonra kaydet

    def _save_now(self):
        self.lbl_status.setText("kaydediliyor…")
        save_notes(self._notes, lambda _: self.lbl_status.setText(""))

    def _add_note(self):
        title, ok = QInputDialog.getText(self, "Yeni Not", "Not başlığı:")
        if not ok or not title.strip():
            return
        self._notes.append({"title": title.strip(), "body": ""})
        self._current = len(self._notes) - 1
        self._refresh_list()
        self._save_now()

    def _delete_note(self):
        if self._current is None:
            return
        self._notes.pop(self._current)
        self._current = None
        self._refresh_list()
        self._save_now()
