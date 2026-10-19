"""Icons used across the app."""

from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QIcon, QPixmap

from dbmanager.config import APP_ICON_PATH

EYE_CLOSED = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C7 5 2.73 8.11 1 12C2.73 15.89 7 19 12 19C17 19 21.27 15.89 23 12C21.27 8.11 17 5 12 5Z"
stroke="#c2c7ce" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M12 15.5C13.933 15.5 15.5 13.933 15.5 12C15.5 10.067 13.933 8.5 12 8.5C10.067 8.5 8.5 10.067 8.5 12C8.5 13.933 10.067 15.5 12 15.5Z"
stroke="#c2c7ce" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

EYE_OPEN = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C7 5 2.73 8.11 1 12C2.73 15.89 7 19 12 19C17 19 21.27 15.89 23 12C21.27 8.11 17 5 12 5Z"
stroke="#374151" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M12 15.5C13.933 15.5 15.5 13.933 15.5 12C15.5 10.067 13.933 8.5 12 8.5C10.067 8.5 8.5 10.067 8.5 12C8.5 13.933 10.067 15.5 12 15.5Z"
stroke="#374151" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def svg_icon(svg: str) -> QIcon:
    """Render an SVG string into a QIcon."""
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(svg.encode("utf-8")), "SVG")
    return QIcon(pixmap)


def app_icon() -> QIcon:
    return QIcon(str(APP_ICON_PATH)) if APP_ICON_PATH.exists() else QIcon()
