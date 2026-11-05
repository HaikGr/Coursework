"""ValuePanel - the whole value of the selected cell, under a data grid whose columns cut long values short."""

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QSplitter, QVBoxLayout
)

from dbmanager.model.table_state import NULL_TEXT
from dbmanager.ui.common.data_grid import SCROLLBAR_STYLE
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.style import MONOSPACE

# The type is cut past this (a MySQL enum lists all its values), whole in its tooltip
TYPE_CHIP_WIDTH = 160
# Its height the first time it opens under a grid; after that, what the user dragged it to
PANEL_HEIGHT = 180

PANEL_STYLE = f"""
    QFrame#valuePanel {{ background-color: #252D3A; border-top: 1px solid #3D4852; }}
    QLabel {{ color: #E2E8F0; background: transparent; font-size: 12px; }}
    QLabel#valueTitle {{ font-weight: 600; }}
    QLabel#valueType {{ background-color: #4A5568; border-radius: 4px; font-size: 10px; padding: 1px 8px; }}
    QLabel#valueWhere, QLabel#valueStatus {{ color: #A0AEC0; font-size: 11px; }}
    QPlainTextEdit {{ background-color: #1A202C; color: #F7FAFC; border: none; padding: 4px 6px;
                      font-family: {MONOSPACE}; font-size: 12px;
                      selection-background-color: #3777f0; selection-color: #FFFFFF; }}
    QPushButton {{ background-color: #4A5568; color: #E2E8F0; border: none; border-radius: 4px;
                   font-size: 11px; padding: 3px 10px; }}
    QPushButton:hover {{ background-color: #5A6A7D; }}
    QPushButton:checked {{ background-color: #3777f0; color: #FFFFFF; }}
    QPushButton:disabled {{ background-color: #2D3748; color: #718096; }}
    QPushButton#valueClose {{ background-color: transparent; color: #A0AEC0; font-size: 13px; padding: 0px 6px; }}
    QPushButton#valueClose:hover {{ background-color: #4A5568; color: #FFFFFF; }}
""" + SCROLLBAR_STYLE

PROBLEM_STYLE = "QLabel { color: #fbbf24; }"


def is_null(value):
    return value is None or (isinstance(value, str) and value.strip().upper() == NULL_TEXT)


class ValuePanel(QFrame):
    """The whole of one value, on as many lines as it has, and room to edit it when its grid allows that.

    The owner says what to show (show_value) and takes the text as it is typed (edited): the panel is a bigger
    editor of the cell, so there is nothing to apply and nothing to lose. set_problem says the text was not
    taken; editing_finished comes when the editor is left for another widget."""

    edited = pyqtSignal(str)          # the text as typed; NULL_TEXT after Set NULL
    editing_finished = pyqtSignal()
    leave_requested = pyqtSignal()    # Esc: back to the grid
    closed = pyqtSignal()             # ✕

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("valuePanel")
        self.setStyleSheet(PANEL_STYLE)
        self._null = False
        self._note = ""
        self._sized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 6, 6, 6)
        header.setSpacing(8)
        self.title = ElidedLabel()
        self.title.setObjectName("valueTitle")
        # As wide as the name when there is room (the type follows it), cut short when there is not
        self.title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.type_chip = QLabel()
        self.type_chip.setObjectName("valueType")
        self.where = QLabel()
        self.where.setObjectName("valueWhere")
        close = QPushButton("✕")
        close.setObjectName("valueClose")
        close.setToolTip("Hide the value panel")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.clicked.connect(self._close)
        header.addWidget(self.title)
        header.addWidget(self.type_chip)
        header.addWidget(self.where)
        header.addStretch(1)
        header.addWidget(close)
        layout.addLayout(header)

        self.editor = QPlainTextEdit()
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        palette = self.editor.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#718096"))
        self.editor.setPalette(palette)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.installEventFilter(self)
        layout.addWidget(self.editor, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(12, 6, 6, 6)
        footer.setSpacing(6)
        self.status = QLabel()
        self.status.setObjectName("valueStatus")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(60)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer.addWidget(self.status, 1)
        # Buttons take no focus: clicking one must not count as leaving the editor (editing_finished)
        self.wrap_btn = self._button("Wrap", "Wrap long lines at the panel's width")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(True)
        self.wrap_btn.toggled.connect(self._set_wrap)
        self.copy_btn = self._button("Copy", "Copy the whole value")
        self.copy_btn.clicked.connect(self._copy)
        self.null_btn = self._button("Set NULL", "Leave this cell without a value")
        self.null_btn.clicked.connect(self._set_null)
        for button in (self.wrap_btn, self.copy_btn, self.null_btn):
            footer.addWidget(button)
        layout.addLayout(footer)

        # "Copied" for a moment, then back to "Copy"
        self._copied = QTimer(self)
        self._copied.setSingleShot(True)
        self._copied.setInterval(1200)
        self._copied.timeout.connect(lambda: self.copy_btn.setText("Copy"))

        self.show_nothing()

    @staticmethod
    def _button(text, tooltip):
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def reveal(self):
        """Show the panel. In a splitter under a grid it takes PANEL_HEIGHT the first time, the grid the rest."""
        if not self.isHidden():
            return
        self.show()
        splitter = self.parentWidget()
        if isinstance(splitter, QSplitter) and not self._sized:
            self._sized = True
            total = sum(splitter.sizes())
            splitter.setSizes([max(total - PANEL_HEIGHT, 0), PANEL_HEIGHT])

    # ---------------- What is shown ----------------
    def show_value(self, title, type_name, value, where="", editable=False, note=""):
        """One cell: its column's name and type, where it is ("row 3"), its value (None or NULL for none).
        note: why it cannot be edited here, when the grid does not make that plain."""
        self.title.setText(title)
        self._set_type(type_name)
        self.where.setText(where)
        self._note = note
        self.editor.setReadOnly(not editable)
        self.null_btn.setVisible(editable)
        self._show_text(None if is_null(value) else str(value))

    def show_nothing(self):
        self.title.setText("No cell selected")
        self._set_type("")
        self.where.setText("")
        self._note = ""
        self.editor.setReadOnly(True)
        self.null_btn.setVisible(False)
        self._show_text(None, placeholder="Select a cell to see its whole value here")
        self.status.setText("")

    def set_problem(self, problem):
        """Why the text typed was not taken, or None once it was"""
        self.status.setText(problem or self._describe())
        self.status.setStyleSheet(PROBLEM_STYLE if problem else "")

    def text(self):
        return self.editor.toPlainText()

    def focus_editor(self):
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_type(self, type_name):
        self.type_chip.setVisible(bool(type_name))
        self.type_chip.ensurePolished()  # its own font size counts
        room = TYPE_CHIP_WIDTH - 2 * 8 - 2
        shown = self.type_chip.fontMetrics().elidedText(type_name, Qt.TextElideMode.ElideRight, room)
        self.type_chip.setText(shown)
        self.type_chip.setToolTip(type_name if shown != type_name else "")

    def _show_text(self, text, placeholder=None):
        self._null = text is None
        self.editor.blockSignals(True)  # what the cell holds already: not an edit
        self.editor.setPlainText(text or "")
        self.editor.blockSignals(False)
        self.editor.setPlaceholderText(placeholder or ("NULL" if self._null else "empty text"))
        self.copy_btn.setEnabled(not self._null)
        self.null_btn.setEnabled(not self._null)
        self.set_problem(None)

    def _describe(self):
        if self._null:
            text = "NULL - no value"
        else:
            count = len(self.editor.toPlainText())
            lines = self.editor.blockCount()
            text = f"{count:,} character{'s' if count != 1 else ''}" + (f" · {lines:,} lines" if lines > 1 else "")
        return f"{text} · {self._note}" if self._note else text

    # ---------------- What is done ----------------
    def _on_text_changed(self):
        self._null = False
        self.editor.setPlaceholderText("empty text")
        self.copy_btn.setEnabled(True)
        self.null_btn.setEnabled(True)
        self.set_problem(None)
        self.edited.emit(self.editor.toPlainText())

    def _set_null(self):
        self._show_text(None)
        self.edited.emit(NULL_TEXT)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.editor.toPlainText())
        self.copy_btn.setText("Copied")
        self._copied.start()

    def _set_wrap(self, wrap):
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if wrap
                                    else QPlainTextEdit.LineWrapMode.NoWrap)

    def _close(self):
        self.hide()
        self.closed.emit()

    def eventFilter(self, watched, event):
        if watched is self.editor:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self.leave_requested.emit()
                    return True
                # A read-only editor lets these through to the page, which takes them for "delete the rows"
                if self.editor.isReadOnly() and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                    return True
            elif event.type() == QEvent.Type.FocusOut and event.reason() not in (
                    Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason):
                # Not another window or the editor's own context menu: the user moved on
                self.editing_finished.emit()
        return super().eventFilter(watched, event)
