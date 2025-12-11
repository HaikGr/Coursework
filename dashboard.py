import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QStackedWidget
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

import sys

from items.TopBar import TopBar
from items.SideBar import SideBar
from items.DiagramPage import DiagramPage
from items.SQLQueryBuilder import SQLQueryBuilder
from windowtransitions import WindowTransition


def get_app_icon():
    """Get the application icon path"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "icon", "sql_query_builder_icon.svg")


class DashboardWindow(QMainWindow):
    def __init__(self, username, parent_window=None, geometry=None):
        super().__init__()
        self.setWindowTitle("SQL Query Builder - Dashboard")
        self.setWindowIcon(QIcon(get_app_icon()))
        self.parent_window = parent_window
        self.username = username
        
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        
        self.setStyleSheet("background-color: #f5f6f7;")
        self.setMinimumSize(1200, 700)
        
        main_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        main_widget.setLayout(root_layout)
        self.setCentralWidget(main_widget)
        
        top_bar = TopBar(username)
        root_layout.addWidget(top_bar)
        
        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(body_layout)
        
        self.stacked_center = QStackedWidget()
        self.stacked_center.setMinimumWidth(900)
        
        self.sidebar_widget = SideBar(self.stacked_center)
        body_layout.addWidget(self.sidebar_widget)
        
        self.sql_builder = SQLQueryBuilder()
        self.diagram_page = DiagramPage(sql_builder=self.sql_builder)
        self.stacked_center.addWidget(self.diagram_page)
        
        add_table_page = QWidget()
        self.stacked_center.addWidget(add_table_page)
        self.add_table_page_index = self.stacked_center.indexOf(add_table_page)
        
        body_layout.addWidget(self.stacked_center, stretch=3)
        body_layout.addWidget(self.sql_builder, stretch=1)
        
        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=400))

    def log_out(self):
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=400)
        else:
            self.close()


# def main():
#     app = QApplication(sys.argv)
#     win = DashboardWindow(username="haik", parent_window=None, geometry=None)
#     win.resize(1400, 860)
#     win.show()
#     sys.exit(app.exec())


# if __name__ == "__main__":
#     main()
