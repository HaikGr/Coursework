from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton

from dbmanager.i18n import tr
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.preferences import PreferencesButtons
from dbmanager.ui.common.style import MENU_STYLE
from dbmanager.ui.common.theme import style

_BUTTON_STYLE = """
    QPushButton {{
        background-color: {background};
        color: {color};
        border: 1px solid @brand_border;
        border-radius: 6px;
        padding: 3px 12px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: @brand_hover; color: @on_brand; }}
"""


class TopBar(QFrame):
    """Title, the way into invitations and premium, the language and theme pickers, and the signed-in user with
    a menu for the account."""
    invitations_clicked = pyqtSignal()
    premium_clicked = pyqtSignal()
    delete_account_clicked = pyqtSignal()
    logout_clicked = pyqtSignal()

    def __init__(self, username):
        super().__init__()
        self.setFixedHeight(40)
        style(self, "QWidget { background-color: @brand; }")
        top_line_layout = QHBoxLayout(self)
        top_line_layout.setContentsMargins(15, 0, 15, 0)
        top_line_layout.setSpacing(10)
        self.title = QLabel()
        bind(self.title.setText, "dashboard.top_bar.title")
        style(self.title, "QLabel { color: @on_brand; font-size: 18px; font-weight: 600; }")
        top_line_layout.addWidget(self.title)
        top_line_layout.addStretch()

        self.invitations_button = self._button("dashboard.top_bar.invitations_tip", self.invitations_clicked)
        top_line_layout.addWidget(self.invitations_button)
        self.premium_button = self._button("dashboard.top_bar.premium_tip", self.premium_clicked)
        top_line_layout.addWidget(self.premium_button)
        top_line_layout.addSpacing(6)
        self.preferences = PreferencesButtons()
        top_line_layout.addWidget(self.preferences)
        top_line_layout.addSpacing(6)

        self.account_menu = QMenu(self)
        style(self.account_menu, MENU_STYLE)
        log_out = self.account_menu.addAction("")
        bind(log_out.setText, "dashboard.top_bar.log_out")
        log_out.triggered.connect(self.logout_clicked)
        self.account_menu.addSeparator()
        delete_account = self.account_menu.addAction("")
        bind(delete_account.setText, "dashboard.top_bar.delete_account")
        delete_account.triggered.connect(self.delete_account_clicked)

        account = QToolButton()
        bind(account.setText, "dashboard.top_bar.account", username=username)
        bind(account.setToolTip, "dashboard.top_bar.account_tip")
        account.setCursor(Qt.CursorShape.PointingHandCursor)
        account.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        account.setMenu(self.account_menu)
        style(account, """
            QToolButton { color: @on_brand; background: transparent; border: none; font-size: 14px; padding: 3px 6px; }
            QToolButton:hover { background-color: @brand_hover; border-radius: 6px; }
            QToolButton::menu-indicator { image: none; }
        """)
        top_line_layout.addWidget(account)

        self.set_pending_invitations(0)
        self.set_premium(False)

    @staticmethod
    def _button(tooltip, signal):
        button = QPushButton()
        bind(button.setToolTip, tooltip)
        button.setFixedHeight(28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(signal)
        return button

    def set_pending_invitations(self, count):
        """Invitations waiting for an answer stand out until they are answered."""
        bind(self.invitations_button.setText,
             lambda: tr("dashboard.top_bar.invitations_count", count=count) if count
             else tr("dashboard.top_bar.invitations"))
        style(self.invitations_button, _BUTTON_STYLE.format(
            background="@highlight" if count else "transparent", color="@on_highlight" if count else "@on_brand"))

    def set_premium(self, premium):
        bind(self.premium_button.setText, "dashboard.top_bar.premium" if premium else "dashboard.top_bar.go_premium")
        style(self.premium_button, _BUTTON_STYLE.format(background="transparent", color="@on_brand"))
