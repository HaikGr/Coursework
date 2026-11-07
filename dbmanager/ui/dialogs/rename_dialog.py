from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QVBoxLayout

from dbmanager.i18n import tr
from dbmanager.ui.common.dark_dialog import settle_enter_key
from dbmanager.ui.common.theme import qss

# The width of the field: a short name gets the usual width, a longer one is shown whole up to the most;
# what goes beyond that scrolls. TEXT_ROOM is the field's padding and border, and room for the cursor.
FIELD_WIDTH, FIELD_MAX_WIDTH, TEXT_ROOM = 310, 600, 32


class RenameDialog(QDialog):
    """One-line input in the current theme. title and prompt are shown as given (already translated)."""

    def __init__(self, parent, title, prompt, current):
        super().__init__(parent)
        self.setWindowTitle(title)
        # QLabel sets its own background: the dialog inherits the style sheet of the page it opens over
        self.setStyleSheet(qss("""
            QDialog { background-color: @surface; }
            QLabel { color: @text; font-size: 14px; background: transparent; }
            QLineEdit {
                background-color: @sunken;
                color: @text;
                border: 2px solid @border_strong;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: @selection;
                selection-color: @on_selection;
            }
            QLineEdit:focus { border: 2px solid @focus; }
            QPushButton {
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                min-width: 80px;
            }
        """))

        layout = QVBoxLayout(self)
        # As big as what it holds: a fixed size squeezed the padded field until its text was cut in half
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(QLabel(prompt))

        self.line_edit = QLineEdit(current)
        self.line_edit.selectAll()
        self.line_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.line_edit)
        self.line_edit.ensurePolished()  # in the dialog now: measured in the font its style sheet gives it
        text_width = self.line_edit.fontMetrics().horizontalAdvance(current) + TEXT_ROOM
        self.line_edit.setMinimumWidth(min(max(FIELD_WIDTH, text_width), FIELD_MAX_WIDTH))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet(qss("QPushButton { background-color: @surface_raised; color: @text; } "
                                     "QPushButton:hover { background-color: @surface_pressed; }"))
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton(tr("common.rename"))
        ok_btn.setStyleSheet(qss("QPushButton { background-color: @accent; color: @on_accent; } "
                                 "QPushButton:hover { background-color: @accent_hover; }"))
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        settle_enter_key(self)  # Enter in the field renames, nothing else
        layout.addLayout(btn_layout)


def ask_new_name(parent, title, prompt, current):
    """Returns the trimmed text, or None when cancelled."""
    dialog = RenameDialog(parent, title, prompt, current)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.line_edit.text().strip()
