from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtCore import Qt, QByteArray, QSize

# Other Windows
from signup import SignUpWindow
from dashboard import DashboardWindow
# Utilities
import animatedbackground as ab


# ---------------------------
# Sign In Window
# ---------------------------

class SignInWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # self.setFixedSize(1200, 700)
        self.setWindowTitle("Database Management")
        self.setStyleSheet("background-color: #3B82F6;")
        self.setMinimumSize(1200, 700)

        # Animated background as central widget
        self.animated_bg = ab.AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Content container sits on top of animated background
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")

        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)

        # ----- Left info -----
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

        # ----- Right Sign In Card -----
        card = QWidget()
        card.setFixedSize(380, 600)
        card.setStyleSheet("background-color: #C5D9F5; border-radius: 40px;")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 50, 30, 30)
        card_layout.setSpacing(20)
    
        heading = QLabel("Welcome Back")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 40px; color: #4B5563; font-weight: bold;")
        card_layout.addWidget(heading)
        plain_text = QLabel("Sign in to continue to your database")
        plain_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plain_text.setStyleSheet("font-size: 15px; color: #838b99;")
        card_layout.addWidget(plain_text)

        # Username
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username or Email")
        self.username.setStyleSheet(
            """
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
        )
        card_layout.addWidget(self.username)
        
        # Password Layout
        password_container = QWidget()
        password_container.setFixedHeight(50)
        password_container.setStyleSheet("background: transparent;")

        self.password = QLineEdit(password_container)
        self.password.setGeometry(0, 0, 320, 50)   # width adjusts inside card
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
            QLineEdit:focus {
                border: 2px solid #93B9E8;
            }
        """)

        self.toggle_btn = QPushButton(password_container)
        self.toggle_btn.setGeometry(270, 8, 34, 34)  # <--- POSITIONED ON TOP
        self.toggle_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))
        self.toggle_btn.setIconSize(QSize(22, 22))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                color: black;
                border: none;
                background: transparent;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_password)

        # Add widgets
        card_layout.addWidget(password_container)

        # Remember + Forgot
        remember_layout = QHBoxLayout()
        remember_layout.setSpacing(10)
        self.remember = QCheckBox("Remember me")
        self.remember.setStyleSheet("color: #8691a0; font-size: 14px;")
        forgot = QPushButton("Forgot password?")
        forgot.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
        remember_layout.addWidget(self.remember)
        remember_layout.addStretch()
        remember_layout.addWidget(forgot)
        card_layout.addLayout(remember_layout)
        card_layout.addSpacing(30)

        # Connect button
        connect_btn = QPushButton("Connect")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3479f3;
                color: white;
                font-size: 18px;
                border-radius: 60px;
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #7BA3D0;
            }
            """
        )
        connect_btn.clicked.connect(self.attempt_signin)
        card_layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # SignUp row (LEFT + RIGHT)
        signup_row = QHBoxLayout()
        lbl = QLabel("Don't have an account?")
        lbl.setStyleSheet("color:#4B5563; font-size:14px;")
        signup_row.addStretch()
        signup_row.addWidget(lbl)

        signup_btn = QPushButton("SIGN UP")
        signup_btn.setStyleSheet("color:#3B82F6; background:transparent; border:none;")
        signup_btn.clicked.connect(self.switch_to_signup)
        signup_row.addWidget(signup_btn)
        signup_row.addStretch()
        signup_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addLayout(signup_row)


        container_layout.addWidget(card, stretch=1)

        # Make content_container fill the animated background
        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_container)

        # Windows
        self.dashboard_window = None
        self.signup_window = None

    # ------------------------
    # Methods
    # ------------------------
    def toggle_password(self):
        if self.password.echoMode() == QLineEdit.EchoMode.Password:
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setIcon(ab.svg_icon(ab.EYE_OPEN))
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setIcon(ab.svg_icon(ab.EYE_CLOSED))

    def switch_to_signup(self, checked=False):
        self.signup_window = SignUpWindow(self, self.saveGeometry())
        self.signup_window.show()
        self.hide()

    def attempt_signin(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Sign In Error")
            msg.setText("Please enter both username/email and password.")
            msg.exec()
            return
        self.dashboard_window = DashboardWindow(username, self, self.saveGeometry())
        self.dashboard_window.show()
        self.hide()
    