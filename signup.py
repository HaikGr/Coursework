"""
Sign Up Window - Original Blue Theme with Smooth Transitions
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer

import animatedbackground as ab
from windowtransitions import WindowTransition


def get_app_icon():
    """Get the application icon path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")


class SignUpWindow(QMainWindow):
    def __init__(self, parent_window, geometry):
        super().__init__()
        self.setWindowTitle("Database Management - Sign Up")
        self.setWindowIcon(QIcon(get_app_icon()))
        self.setStyleSheet("background-color: #3B82F6;")
        self.parent_window = parent_window
        self.saved_geometry = geometry
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        self.setMinimumSize(1200, 700)

        # Animated background as central widget
        self.animated_bg = ab.AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Content container
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")

        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)

        # Left side
        left = QVBoxLayout()
        left.setContentsMargins(0, 160, 0, 0)
        left.setSpacing(25)

        title = QLabel("Database\nManagement")
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")
        desc = QLabel(
            "Visualize, manage, and optimize your databases\nwith powerful ERD tools and real-time collaboration"
        )
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 18px;")
        desc.setWordWrap(True)

        feat1 = QLabel("✔ Interactive ERD Builder")
        feat1.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 16px;")
        feat2 = QLabel("✔ Table Relationships")
        feat2.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 16px;")

        left.addWidget(title)
        left.addWidget(desc)
        left.addWidget(feat1)
        left.addWidget(feat2)
        left.addStretch()
        container_layout.addLayout(left, stretch=2)

        # Card
        card = QWidget()
        card.setFixedWidth(380)
        card.setFixedHeight(600)
        card.setStyleSheet("background-color: #C5D9F5; border-radius: 40px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)

        # Heading
        heading = QLabel("Connect Database")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 32px; color: #4B5563; margin-bottom: 20px; font-weight: bold;")
        card_layout.addSpacing(-10)
        card_layout.addWidget(heading)
        card_layout.addSpacing(-25)

        # Text
        databasetext = QLabel("Enter your database connection details")
        databasetext.setStyleSheet("font-size: 15px; color: #838b99;")
        databasetext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(databasetext)
        card_layout.addSpacing(5)

        input_style = """
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """

        # Username
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setStyleSheet(input_style)
        card_layout.addWidget(self.username)

        # Password with toggle
        password_container = QWidget()
        password_container.setFixedHeight(50)
        password_container.setStyleSheet("background: transparent;")

        self.password = QLineEdit(password_container)
        self.password.setGeometry(0, 0, 320, 50)
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setStyleSheet(input_style)

        self.password_btn = QPushButton(password_container)
        self.password_btn.setGeometry(270, 8, 34, 34)
        self.password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        self.password_btn.setIconSize(QSize(22, 22))
        self.password_btn.setStyleSheet("""
            QPushButton { color: black; border: none; background: transparent; }
        """)
        self.password_btn.clicked.connect(self.toggle_password_main)
        card_layout.addWidget(password_container)

        # Host
        self.host = QLineEdit()
        self.host.setPlaceholderText("Host (e.g., localhost)")
        self.host.setStyleSheet(input_style)
        card_layout.addWidget(self.host)

        # Port
        self.port = QLineEdit()
        self.port.setPlaceholderText("Port (e.g., 5432)")
        self.port.setStyleSheet(input_style)
        card_layout.addWidget(self.port)

        # Database Name
        self.databasename = QLineEdit()
        self.databasename.setPlaceholderText("Database Name")
        self.databasename.setStyleSheet(input_style)
        card_layout.addWidget(self.databasename)

        # Database Password with toggle
        db_pwd_container = QWidget()
        db_pwd_container.setFixedHeight(50)
        db_pwd_container.setStyleSheet("background: transparent;")

        self.db_password = QLineEdit(db_pwd_container)
        self.db_password.setGeometry(0, 0, 320, 50)
        self.db_password.setPlaceholderText("Database Password")
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_password.setStyleSheet(input_style)

        self.db_password_btn = QPushButton(db_pwd_container)
        self.db_password_btn.setGeometry(270, 8, 34, 34)
        self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        self.db_password_btn.setIconSize(QSize(22, 22))
        self.db_password_btn.setStyleSheet("""
            QPushButton { color: black; border: none; background: transparent; }
        """)
        self.db_password_btn.clicked.connect(self.toggle_password_db)
        card_layout.addWidget(db_pwd_container)

        # Circle Connect button
        connect_btn = QPushButton("Connect")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3479f3;
                color: white;
                font-size: 18px;
                border-radius: 60px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7BA3D0; }
        """)
        card_layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Sign in link
        signup = QPushButton("SIGN IN")
        signup.setStyleSheet("color:#3B82F6; background:transparent; border:none;")
        signup.clicked.connect(self.go_back)
        card_layout.addWidget(signup, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(-15)

        container_layout.addWidget(card, stretch=1)

        # Main layout
        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_container)

        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=350))

    def toggle_password_main(self):
        if self.password.echoMode() == QLineEdit.EchoMode.Password:
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.password_btn.setIcon(ab.svg_icon(ab.EYE_OPEN))
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))

    def toggle_password_db(self):
        if self.db_password.echoMode() == QLineEdit.EchoMode.Password:
            self.db_password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_OPEN))
        else:
            self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
            self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))

    def go_back(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=450)
        else:
            self.close()
