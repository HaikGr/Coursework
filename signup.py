import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox
)
from PyQt6.QtGui import QIcon, QColor, QPainter, QPixmap
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

import animatedbackground as ab

# ---------------------------
# Sign Up Window
# ---------------------------
class SignUpWindow(QMainWindow):
    def __init__(self, parent_window):
        super().__init__()
        self.setFixedSize(1200, 700)
        self.setWindowTitle("Database Management")
        self.setStyleSheet("background-color: #3B82F6;")
        self.parent_window = parent_window

        central = QWidget()
        self.setCentralWidget(central)


        # Animated background as central widget
        self.animated_bg = ab.AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Content container sits on top of animated background
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")

        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)

        main_layout = QHBoxLayout(central)

        # ===== Left side (Title & Features) =====
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
        # card_layout.setSpacing(20)

        #Heading Field
        heading = QLabel("Connect Database")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 32px; color: #4B5563; margin-bottom: 20px; font-weight: bold;")
        card_layout.addSpacing(-10)
        card_layout.addWidget(heading)
        card_layout.addSpacing(-25)

        # Text Field
        databasetext = QLabel("Enter your database connection details")
        databasetext.setStyleSheet("font-size: 15px; color: #838b99;")
        databasetext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(databasetext)
        card_layout.addSpacing(5)

        # Username
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)
        card_layout.addWidget(self.username)

        # ----------------------
        # First Password (User Password)
        # ----------------------
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)

        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)

        pwd_layout.addWidget(self.password)

        self.password_btn = QPushButton()
        self.password_btn.setFixedSize(36, 36)
        self.password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        self.password_btn.setIconSize(QSize(22, 22))
        self.password_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding-right: 10px;
            }
        """)
        self.password_btn.clicked.connect(self.toggle_password_main)

        pwd_layout.addWidget(self.password_btn)
        card_layout.addWidget(pwd_container)

        # host
        self.host = QLineEdit()
        self.host.setPlaceholderText("Host (e.g., localhost)")
        self.host.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)
        card_layout.addWidget(self.host)

        # Port Field
        self.port = QLineEdit()
        self.port.setPlaceholderText("Port (e.g., 5432)")
        self.port.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)  
        card_layout.addWidget(self.port)    

        # Database Name
        self.databasename = QLineEdit()
        self.databasename.setPlaceholderText("Database Name")
        self.databasename.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)            
        card_layout.addWidget(self.databasename)

        # Password with toggle
        self.db_password = QLineEdit()
        self.db_password.setPlaceholderText("Database Password")
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_password.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid transparent;
                border-radius: 24px;
                padding: 12px 20px;
                font-size: 16px;
                color: #4B5563;
            }
            QLineEdit:focus { border: 2px solid #93B9E8; }
        """)

        db_pwd_container = QWidget()
        db_pwd_layout = QHBoxLayout(db_pwd_container)
        db_pwd_layout.setContentsMargins(0, 0, 0, 0)

        db_pwd_layout.addWidget(self.db_password)

        self.db_password_btn = QPushButton()
        self.db_password_btn.setFixedSize(36, 36)
        self.db_password_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        self.db_password_btn.setIconSize(QSize(22, 22))
        self.db_password_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding-right: 10px;
            }
        """)
        self.db_password_btn.clicked.connect(self.toggle_password_db)

        db_pwd_layout.addWidget(self.db_password_btn)
        card_layout.addWidget(db_pwd_container)

        # Circle Connect button
        connect_btn = QPushButton("Connect")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #93B9E8, stop:1 #7BA3D0);
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
        main_layout.setContentsMargins(40, 20, 100, 100)

        # Make content_container fill the animated background
        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_container)

    # methods
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
        """Hides this window and re-shows the parent Sign In window."""
        if self.parent_window:
            self.parent_window.show()
        self.close()