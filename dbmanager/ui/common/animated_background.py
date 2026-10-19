"""Starry blue background (constellation effect) behind the sign-in screens."""

import math
import random

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

BACKGROUND_COLOR = "#3B82F6"
FRAME_INTERVAL_MS = 16
LINK_DISTANCE = 120


class Star:
    """A single star particle."""

    def __init__(self, width, height):
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.z = random.uniform(0.1, 1.0)
        self.size = 2 + (1 - self.z) * 4
        self.speed = (1.0 + (1 - self.z) * 1.5) / 5
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
        painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawEllipse(QPointF(self.x, self.y), self.size / 2, self.size / 2)


class AnimatedBackground(QWidget):
    """Moving stars joined by lines when they come close. Animates only while visible."""

    def __init__(self, parent=None, star_count=60):
        super().__init__(parent)
        self.stars = [Star(1200, 700) for _ in range(star_count)]
        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_INTERVAL_MS)
        self.timer.timeout.connect(self.update_animation)

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        # The window stays alive (hidden) behind the dashboard: do not keep painting at 60 fps
        self.timer.stop()
        super().hideEvent(event)

    def update_animation(self):
        width, height = self.width(), self.height()
        for star in self.stars:
            star.update(width, height)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(event.rect(), QColor(BACKGROUND_COLOR))

        for star in self.stars:
            star.draw(painter)

        for i, star1 in enumerate(self.stars):
            for star2 in self.stars[i + 1:]:
                distance = math.hypot(star1.x - star2.x, star1.y - star2.y)
                if distance < LINK_DISTANCE:
                    alpha = int(255 * (1 - distance / LINK_DISTANCE))
                    pen = QPen(QColor(255, 255, 255, alpha))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawLine(QPointF(star1.x, star1.y), QPointF(star2.x, star2.y))
