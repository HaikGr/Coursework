from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton

_BUTTON_STYLE = """
    QPushButton {{
        background-color: {background};
        color: {color};
        border: 1px solid rgba(255, 255, 255, 0.6);
        border-radius: 6px;
        padding: 3px 12px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.25); color: white; }}
"""


class TopBar(QFrame):
    """Title, the way into invitations and premium, and the signed-in user with a menu for the account."""
    invitations_clicked = pyqtSignal()
    premium_clicked = pyqtSignal()
    delete_account_clicked = pyqtSignal()
    logout_clicked = pyqtSignal()

    def __init__(self, username):
        super().__init__()
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #3777f0;")
        top_line_layout = QHBoxLayout(self)
        top_line_layout.setContentsMargins(15, 0, 15, 0)
        top_line_layout.setSpacing(10)
        title = QLabel("Database Management System")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        top_line_layout.addWidget(title)
        top_line_layout.addStretch()

        self.invitations_button = self._button("Databases other users share with you", self.invitations_clicked)
        top_line_layout.addWidget(self.invitations_button)
        self.premium_button = self._button("Verify an email address to share your databases",
                                           self.premium_clicked)
        top_line_layout.addWidget(self.premium_button)
        top_line_layout.addSpacing(6)

        self.account_menu = QMenu(self)
        self.account_menu.setStyleSheet("""
            QMenu { background-color: #FFFFFF; color: #2D3748; border: 1px solid #CBD5E0; padding: 4px; }
            QMenu::item { padding: 6px 18px; border-radius: 4px; font-size: 13px; }
            QMenu::item:selected { background-color: #3777f0; color: white; }
        """)
        self.account_menu.addAction("Log out").triggered.connect(self.logout_clicked)
        self.account_menu.addSeparator()
        self.account_menu.addAction("Delete account…").triggered.connect(self.delete_account_clicked)

        account = QToolButton()
        account.setText(f"Connected User: {username}  ▾")
        account.setToolTip("Log out, or delete your account")
        account.setCursor(Qt.CursorShape.PointingHandCursor)
        account.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        account.setMenu(self.account_menu)
        account.setStyleSheet("""
            QToolButton { color: white; background: transparent; border: none; font-size: 14px; padding: 3px 6px; }
            QToolButton:hover { background-color: rgba(255, 255, 255, 0.2); border-radius: 6px; }
            QToolButton::menu-indicator { image: none; }
        """)
        top_line_layout.addWidget(account)

        self.set_pending_invitations(0)
        self.set_premium(False)

    @staticmethod
    def _button(tooltip, signal):
        button = QPushButton()
        button.setToolTip(tooltip)
        button.setFixedHeight(28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(signal)
        return button

    def set_pending_invitations(self, count):
        """Invitations waiting for an answer stand out until they are answered."""
        self.invitations_button.setText(f"✉  Invitations ({count})" if count else "✉  Invitations")
        self.invitations_button.setStyleSheet(_BUTTON_STYLE.format(
            background="#fbc840" if count else "transparent", color="#744210" if count else "white"))

    def set_premium(self, premium):
        self.premium_button.setText("★  Premium" if premium else "☆  Go Premium")
        self.premium_button.setStyleSheet(_BUTTON_STYLE.format(background="transparent", color="white"))
