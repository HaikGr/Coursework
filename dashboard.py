# dashboard.py
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QStackedWidget
)

import sys

from items.TopBar import TopBar
from items.SideBar import SideBar
from items.DiagramPage import DiagramPage
from items.SQLQueryBuilder import SQLQueryBuilder


# ---------------------------
# Main Dashboard Window
# ---------------------------
class DashboardWindow(QMainWindow):
    def __init__(self, username, parent_window=None, geometry=None):
        super().__init__()
        self.setWindowTitle("Database Dashboard - Connected")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        self.setStyleSheet("background-color: #f5f6f7;")
        self.parent_window = parent_window
        self.username = username
     
        main_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        main_widget.setLayout(root_layout)
        self.setCentralWidget(main_widget)

        top_line = TopBar(username)
        root_layout.addWidget(top_line)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(body_layout)
        root_layout.setSpacing(0)

        self.stacked_center = QStackedWidget()
        self.stacked_center.setMinimumWidth(900)

        self.sidebar_widget = SideBar(self.stacked_center)
        body_layout.addWidget(self.sidebar_widget)

        # Create SQL builder first
        self.sql_builder = SQLQueryBuilder()

        # Pass SQL builder to DiagramPage
        self.diagram_page = DiagramPage(sql_builder=self.sql_builder)
        self.stacked_center.addWidget(self.diagram_page)

        add_table_page = QWidget()
        self.stacked_center.addWidget(add_table_page)
        self.add_table_page_index = self.stacked_center.indexOf(add_table_page)

        body_layout.addWidget(self.stacked_center, stretch=3)

        # Add the SQL builder to the layout
        body_layout.addWidget(self.sql_builder, stretch=1)

        
    def log_out(self):
        if self.parent_window:
            self.parent_window.show()
        self.close()

# ---------------------------
# App bootstrap
# ---------------------------
def main():
    app = QApplication(sys.argv)
    win = DashboardWindow(username="haik", parent_window=None, geometry=None)
    win.resize(1400, 860)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()