import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox
)
from PyQt6.QtGui import QIcon, QColor, QPainter, QPixmap
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

# import test
from signin import SignInWindow


def get_app_icon():
    """Get the application icon path"""
    # Get the directory where main.py is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")
    return icon_path


# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application-wide icon
    icon_path = get_app_icon()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    win = SignInWindow()
    win.show()
    sys.exit(app.exec())



