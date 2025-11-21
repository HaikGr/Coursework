from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QGridLayout
from PyQt6.QtCore import Qt

# ---------------------------
# Dashboard Window
# ---------------------------
class DashboardWindow(QMainWindow):
    """
    The main application interface, opened after successful sign-in/connection.
    """
    def __init__(self, username):
        super().__init__()
        self.setWindowTitle("Database Dashboard - Connected")
        self.setFixedSize(1200, 700)
        self.setStyleSheet("background-color: #F0F4F8;")
