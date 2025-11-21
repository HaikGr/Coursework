import sys
import random
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QByteArray, QTimer, QPointF
)

# Assuming SignUpWindow and DashboardWindow exist and contain the necessary methods
from signup import SignUpWindow
from dashboard import DashboardWindow

# --- Star Animation Components ---

class Star:
    """Represents a single star particle."""
    def __init__(self, width, height):
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.z = random.uniform(0.1, 1.0)
        self.size = 2 + (1 - self.z) * 4
        self.speed = (1.0 + (1 - self.z) * 1.5)/5
        angle = random.uniform(0, 2 * math.pi)
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed

    def update(self, width, height):
        self.x += self.vx
        self.y += self.vy
        if self.x < -self.size:
            self.x = width + self.size
        elif self.x > width + self.size:
            self.x = -self.size
        if self.y < -self.size:
            self.y = height + self.size
        elif self.y > height + self.size:
            self.y = -self.size

    def draw(self, painter):
        alpha = int(255 * (1 - self.z * 0.5))
        color = QColor(255, 255, 255, alpha)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(QPointF(self.x, self.y), self.size / 2, self.size / 2)


class AnimatedBackground(QWidget):
    """Starry background with connecting lines (constellation effect)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stars = []
        self.num_stars = 50
        self.width = 1200
        self.height = 700
        self._initialize_stars()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # ~60 FPS

    def _initialize_stars(self):
        for _ in range(self.num_stars):
            self.stars.append(Star(self.width, self.height))

    def update_animation(self):
        self.width = self.size().width()
        self.height = self.size().height()
        for star in self.stars:
            star.update(self.width, self.height)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(event.rect(), QColor("#3B82F6"))

        # Draw stars
        for star in self.stars:
            star.draw(painter)

        # Draw lines between close stars
        max_distance = 120  # Max distance to draw a line
        for i, star1 in enumerate(self.stars):
            for star2 in self.stars[i+1:]:
                dx = star1.x - star2.x
                dy = star1.y - star2.y
                dist = math.hypot(dx, dy)
                if dist < max_distance:
                    # Opacity decreases with distance
                    alpha = int(255 * (1 - dist / max_distance))
                    pen = QPen(QColor(255, 255, 255, alpha))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(QPointF(star1.x, star1.y), QPointF(star2.x, star2.y))

# --- Sign In Window (Updated with Animation and Transitions) ---

class SignInWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 700)
        self.setWindowTitle("Database Management - Sign In")
        
        self.dashboard_window = None
        self.signup_window = None
        self.fade_animation = None

        # Animated background as central widget
        self.animated_bg = AnimatedBackground(self)
        self.setCentralWidget(self.animated_bg)

        # Use a layout on animated_bg to hold the content
        self.content_container = QWidget(self.animated_bg)
        self.content_container.setStyleSheet("background-color: transparent;")
        container_layout = QHBoxLayout(self.content_container)
        container_layout.setContentsMargins(40, 20, 100, 20)

        # Left side (info)
        left = QVBoxLayout()
        title = QLabel("Database Management")
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
        left.addSpacing(200)
        left.addWidget(title)
        left.addSpacing(20)
        left.addWidget(desc)
        left.addSpacing(30)
        left.addWidget(feat1)
        left.addWidget(feat2)
        left.addStretch()

        container_layout.addLayout(left, stretch=2)

        # Right side (Sign In card)
        card = self._create_signin_card()
        container_layout.addWidget(card, stretch=1)

        # Make the content_container fill the animated_bg using layout
        main_layout = QVBoxLayout(self.animated_bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_container)

    def _create_signin_card(self):
        """Creates the Sign In card widget."""
        card = QWidget()
        card.setFixedWidth(440)
        card.setFixedHeight(650)
        card.setStyleSheet("background-color: #C5D9F5; border-radius: 40px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 40, 40, 40)

        heading = QLabel("SIGN IN")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 32px; color: #4B5563; margin-bottom: 20px;")
        layout.addWidget(heading)

        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        self.username_input.setStyleSheet(
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
        layout.addWidget(self.username_input)

        # Password + toggle
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(
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

        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setFixedSize(48, 48)
        self.toggle_btn.setStyleSheet(
            """
            QPushButton {
                background: #E0E7FF;
                border: none;
                border-radius: 24px;
                font-size: 18px;
                color: #4B5563;
            }
            QPushButton:hover { background: #CCD6FF; }
            """
        )
        self.toggle_btn.clicked.connect(self.toggle_password)

        pass_widget = QWidget()
        pass_layout = QHBoxLayout(pass_widget)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.addWidget(self.password_input)
        pass_layout.addWidget(self.toggle_btn)
        layout.addWidget(pass_widget)

        # Remember me + forgot
        remember_layout = QHBoxLayout()
        self.remember = QCheckBox("Remember me")
        self.remember.setStyleSheet("color: #4B5563; font-size: 14px;")
        forgot = QPushButton("Forgot password?")
        forgot.setStyleSheet(
            "color: #3B82F6; background: transparent; border: none;"
        )
        remember_layout.addWidget(self.remember)
        remember_layout.addStretch()
        remember_layout.addWidget(forgot)
        layout.addLayout(remember_layout)

        # Connect button
        connect_btn = QPushButton("Connect →")
        connect_btn.setFixedSize(120, 120)
        connect_btn.setStyleSheet(
            """
            QPushButton {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B82F6, stop:1 #4F46E5); 
                color: white;
                font-size: 18px;
                border-radius: 60px;
                font-weight: bold;
                margin-top: 30px;
            }
            QPushButton:hover { background-color: #4F46E5; }
            """
        )
        connect_btn.clicked.connect(self.attempt_signin)
        layout.addWidget(connect_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        # Sign up link
        signup_label = QLabel("Don't have an account?")
        signup_label.setStyleSheet("color: #4B5563; font-size: 14px;")
        signup_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(signup_label)

        signup_btn = QPushButton("SIGN UP")
        signup_btn.setStyleSheet(
            "color: #3B82F6; background: transparent; border: none; font-size: 14px; font-weight: bold;"
        )
        signup_btn.clicked.connect(self.start_fade_out)
        layout.addWidget(signup_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return card

    # toggle_password, start_fade_out, _perform_switch_to_signup, attempt_signin remain unchanged


    def toggle_password(self):
        """Toggles the visibility of the password."""
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("🔒")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("👁")

    def start_fade_out(self, checked):
        """
        Starts the fade-out animation for the current window (Sign In).
        """
        self.fade_animation = QPropertyAnimation(self, QByteArray(b"windowOpacity"))
        self.fade_animation.setDuration(300) # 300 milliseconds
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Connect the finish signal to the actual switch
        self.fade_animation.finished.connect(self._perform_switch_to_signup)
        self.fade_animation.start()

    def _perform_switch_to_signup(self):
        """Opens the signup window and finalizes the transition."""
        # Note: SignUpWindow must have a start_fade_in method
        self.signup_window = SignUpWindow(self) 
        self.signup_window.start_fade_in() 
        self.hide()
        
    def attempt_signin(self):
        """
        Simulates sign-in, validates fields, and transitions to the dashboard.
        """
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Sign In Error")
            msg.setText("Please enter both username/email and password.")
            msg.exec()
            return
            
        # Success: Transition to Dashboard
        self.dashboard_window = DashboardWindow(username)
        self.dashboard_window.show()
        self.close()