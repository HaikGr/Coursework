"""
Forgot Password Window - Original Blue Theme with Smooth Transitions
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtCore import Qt, QTimer

import animatedbackground as ab
from windowtransitions import WindowTransition


def get_app_icon():
    """Get the application icon path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")


class ForgotPasswordWindow(QMainWindow):
    def __init__(self, parent_window, geometry):
        super().__init__()
        self.setWindowTitle("Database Management - Forgot Password")
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

        # Animated background
        self.animated_bg = ab.AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Content container
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")

        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(60, 60, 60, 60)
        container_layout.setSpacing(50)

        # Left info
        left = QVBoxLayout()
        left.setContentsMargins(0, 160, 0, 0)
        left.setSpacing(25)

        title = QLabel("Database\nManagement")
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")
        desc = QLabel(
            "Enter your email to reset your password\nand regain access to your database"
        )
        desc.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 18px;")
        desc.setWordWrap(True)

        left.addWidget(title)
        left.addWidget(desc)
        left.addStretch()
        container_layout.addLayout(left, stretch=2)

        # Right Forgot Password Card
        card = QWidget()
        card.setFixedSize(380, 400)
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
    
        heading = QLabel("Forgot Password?")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 32px; color: #4B5563; font-weight: bold;")
        card_layout.addWidget(heading)
        
        plain_text = QLabel("Enter your email to receive a reset link")
        plain_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plain_text.setStyleSheet("font-size: 15px; color: #838b99;")
        card_layout.addWidget(plain_text)

        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")
        self.email_input.setStyleSheet("""
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
        card_layout.addWidget(self.email_input)
        card_layout.addSpacing(20)

        # Send Reset Link button
        send_btn = QPushButton("Send Reset Link")
        send_btn.setFixedSize(200, 50)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3479f3;
                color: white;
                font-size: 16px;
                border-radius: 25px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7BA3D0; }
        """)
        send_btn.clicked.connect(self.send_reset_link)
        card_layout.addWidget(send_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Back to Sign In
        back_to_signin_btn = QPushButton("Back to Sign In")
        back_to_signin_btn.setStyleSheet("color:#3B82F6; background:transparent; border:none;")
        back_to_signin_btn.clicked.connect(self.go_back)
        card_layout.addWidget(back_to_signin_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        container_layout.addWidget(card, stretch=1)

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

    def send_reset_link(self):
        email = self.email_input.text().strip()
        if not email:
            QMessageBox.warning(self, "Input Error", "Please enter your email address.")
            return
        if "@" not in email or "." not in email:
            QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return
        
        QMessageBox.information(self, "Password Reset", f"A password reset link has been sent to {email}.")
        self.go_back()

    def go_back(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=450)
        else:
            self.close()
