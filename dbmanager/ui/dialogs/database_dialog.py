from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from dbmanager.api import DB_TYPES, DEFAULT_PORTS, ApiError, parse_port
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.message_box import show_styled_message


class InputDatabaseWindow(QDialog):
    """Dark themed dialog for registering or editing a database connection.

    on_submit(details) is called when the user confirms; if it raises ApiError the
    message is shown and the dialog stays open so the input can be corrected.
    """

    def __init__(self, parent=None, title="New Database", connection=None, button_text="Connect", on_submit=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setFixedSize(420, 540)
        self.return_data = None
        self.on_submit = on_submit
        self.editing = connection is not None

        # Remove window frame for cleaner look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                border: 2px solid #0ea5e9;
                border-radius: 16px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit, QComboBox {
                background-color: #0f172a;
                border: 2px solid #334155;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #0ea5e9;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f1f5f9;
                selection-background-color: #0ea5e9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        # Header
        header = QLabel(f"{title}")
        header.setStyleSheet("""
            color: #f1f5f9;
            font-size: 20px;
            font-weight: bold;
            background: transparent;
        """)
        layout.addWidget(header)
        layout.addSpacing(8)

        # Type
        self.type_combo = QComboBox()
        for value, label, _ in DB_TYPES:
            self.type_combo.addItem(label, value)
        self.type_combo.setFixedHeight(40)
        self._add_field(layout, "Database Type", self.type_combo)

        # Host + Port
        self.host_input = self._line_edit("localhost")
        self.port_input = self._line_edit("")
        self.port_input.setFixedWidth(110)
        host_col = QVBoxLayout()
        host_col.setSpacing(6)
        host_col.addWidget(QLabel("Host"))
        host_col.addWidget(self.host_input)
        port_col = QVBoxLayout()
        port_col.setSpacing(6)
        port_col.addWidget(QLabel("Port"))
        port_col.addWidget(self.port_input)
        host_row = QHBoxLayout()
        host_row.setSpacing(12)
        host_row.addLayout(host_col)
        host_row.addLayout(port_col)
        layout.addLayout(host_row)
        layout.addSpacing(4)

        self.name_input = self._line_edit("my_database")
        self._add_field(layout, "Database Name", self.name_input)

        self.user_input = self._line_edit("Database user")
        self._add_field(layout, "Username", self.user_input)

        self.password_input = self._line_edit(
            "Leave empty to keep the current password" if self.editing else "Database password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.accept)
        self._add_field(layout, "Password", self.password_input)

        if connection:
            index = self.type_combo.findData(connection.get("dbType"))
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            self.host_input.setText(connection.get("host", ""))
            self.port_input.setText(str(connection.get("port", "")))
            self.name_input.setText(connection.get("dbName", ""))
            self.user_input.setText(connection.get("dbUsername", ""))
        else:
            self.port_input.setText(str(DEFAULT_PORTS[self.type_combo.currentData()]))
        self._last_default_port = str(DEFAULT_PORTS[self.type_combo.currentData()])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 42)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #94a3b8;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #475569;
                color: #f1f5f9;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton(button_text)
        ok_btn.setFixedSize(140, 42)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #38bdf8;
            }
        """)
        ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        self.host_input.setFocus()

    @staticmethod
    def _line_edit(placeholder):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(40)
        return field

    @staticmethod
    def _add_field(layout, label_text, widget):
        layout.addWidget(QLabel(label_text))
        layout.addWidget(widget)
        layout.addSpacing(4)

    def _on_type_changed(self):
        # Follow the default port of the chosen type unless the user typed their own
        new_default = str(DEFAULT_PORTS[self.type_combo.currentData()])
        if self.port_input.text().strip() in ("", self._last_default_port):
            self.port_input.setText(new_default)
        self._last_default_port = new_default

    def _error(self, text):
        show_styled_message(self, "Database", text, QMessageBox.Icon.Warning)

    def accept(self):
        host = self.host_input.text().strip()
        port = self.port_input.text().strip()
        name = self.name_input.text().strip()
        user = self.user_input.text().strip()
        password = self.password_input.text()

        if not host or not name or not user:
            self._error("Please fill in host, database name and username.")
            return
        port = parse_port(port)
        if port is None:
            self._error("Port must be a number between 1 and 65535.")
            return
        if not password and not self.editing:
            self._error("Please enter the database password.")
            return

        details = {
            "host": host,
            "port": port,
            "dbName": name,
            "dbUsername": user,
            "dbType": self.type_combo.currentData(),
        }
        if password:
            details["dbPassword"] = password

        if self.on_submit:
            try:
                with busy_cursor():
                    self.on_submit(details)
            except ApiError as error:
                self._error(str(error))
                return

        self.return_data = details
        super().accept()

    def get_data(self):
        return self.return_data
