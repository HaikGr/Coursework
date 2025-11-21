import random
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QIcon, QPixmap
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QByteArray, QTimer, QPointF
)

EYE_CLOSED = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"
xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C7 5 2.73 8.11 1 12C2.73 15.89 7 19 12 19C17 19 21.27 15.89 23 12C21.27 8.11 17 5 12 5Z"
stroke="#c2c7ce" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M12 15.5C13.933 15.5 15.5 13.933 15.5 12C15.5 10.067 13.933 8.5 12 8.5C10.067 8.5 8.5 10.067 8.5 12C8.5 13.933 10.067 15.5 12 15.5Z"
stroke="#c2c7ce" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

EYE_OPEN = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"
xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C7 5 2.73 8.11 1 12C2.73 15.89 7 19 12 19C17 19 21.27 15.89 23 12C21.27 8.11 17 5 12 5Z"
stroke="#374151" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M12 15.5C13.933 15.5 15.5 13.933 15.5 12C15.5 10.067 13.933 8.5 12 8.5C10.067 8.5 8.5 10.067 8.5 12C8.5 13.933 10.067 15.5 12 15.5Z"
stroke="#374151" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

def svg_icon(svg: str) -> QIcon:
    """Render SVG string into a QIcon."""
    data = QByteArray(svg.encode("utf-8"))
    pix = QPixmap()
    pix.loadFromData(data, "SVG")
    return QIcon(pix)

# ---------------------------
# Star + Animated Background
# ---------------------------
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
        self.num_stars = 60
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
        max_distance = 120
        for i, star1 in enumerate(self.stars):
            for star2 in self.stars[i + 1:]:
                dx = star1.x - star2.x
                dy = star1.y - star2.y
                dist = math.hypot(dx, dy)
                if dist < max_distance:
                    alpha = int(255 * (1 - dist / max_distance))
                    pen = QPen(QColor(255, 255, 255, alpha))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(QPointF(star1.x, star1.y), QPointF(star2.x, star2.y))