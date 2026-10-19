"""Forgot Password window."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QMessageBox, QPushButton

from dbmanager.ui.auth.base import INPUT_STYLE, LINK_BUTTON_STYLE, AuthWindow, primary_button_style


class ForgotPasswordWindow(AuthWindow):
    def __init__(self, parent_window, geometry):
        super().__init__("Database Management - Forgot Password", card_height=400,
                         card_margins=(30, 50, 30, 30), card_spacing=20,
                         description="Enter your email to reset your password\nand regain access to your database",
                         features=[], parent_window=parent_window, geometry=geometry)
        self.add_heading("Forgot Password?", 32, "Enter your email to receive a reset link")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")
        self.email_input.setStyleSheet(INPUT_STYLE)
        self.email_input.returnPressed.connect(self.send_reset_link)
        self.card_layout.addWidget(self.email_input)
        self.card_layout.addSpacing(20)

        send_btn = QPushButton("Send Reset Link")
        send_btn.setFixedSize(200, 50)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(primary_button_style(radius=25, font_size=16))
        send_btn.clicked.connect(self.send_reset_link)
        self.card_layout.addWidget(send_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        back_btn = QPushButton("Back to Sign In")
        back_btn.setStyleSheet(LINK_BUTTON_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back)
        self.card_layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def send_reset_link(self):
        email = self.email_input.text().strip()
        if not email:
            QMessageBox.warning(self, "Input Error", "Please enter your email address.")
            return
        local, _, domain = email.partition("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return

        # The backend has no password-reset endpoint yet, so nothing can be sent.
        QMessageBox.information(
            self, "Password Reset",
            "Password reset by email is not available yet.\n"
            "You can still sign in with your username or email and your current password."
        )
        self.go_back()
