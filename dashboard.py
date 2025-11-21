import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QScrollArea, QFrame
)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QPoint

# ---------------------------
# Draggable Table Card Widget
# ---------------------------
class TableCard(QFrame):
    def __init__(self, table_name, fields):
        super().__init__()
        self.table_name = table_name
        self.fields = fields
        self.setFixedSize(230, 180)

        self.setStyleSheet("""
            QFrame {
                background-color: #2E3641;
                border-radius: 8px;
                border: 1px solid #4A4F55;
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout()
        title = QLabel(table_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        for f in fields:
            lbl = QLabel(f"• {f}")
            lbl.setStyleSheet("color: #C6C6C6; font-size: 13px;")
            layout.addWidget(lbl)

        layout.addStretch()
        self.setLayout(layout)

        self.drag_pos = None

    # Dragging widget
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

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
        # self.setFixedSize(1200, 700)
        # self.setStyleSheet("background-color: #F0F4F8;")
        self.setGeometry(200, 100, 1600, 900)
        self.setStyleSheet("background-color: #1C1F26;")

        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # -----------------------------
        # Left Sidebar
        # -----------------------------
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(10, 10, 10, 10)

        lbl_db = QLabel("Databases")
        lbl_db.setStyleSheet("font-size: 18px; color: white; font-weight: bold;")
        sidebar.addWidget(lbl_db)

        self.db_list = QListWidget()
        self.db_list.setStyleSheet("""
            QListWidget {
                background-color: #252A33;
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
            QListWidget::item:selected {
                background-color: #3C4450;
            }
        """)
        sidebar.addWidget(self.db_list)

        self.db_list.addItem("Database 1")
        self.db_list.addItem("Database 2")
        self.db_list.setFixedWidth(220)

        sidebar.addStretch()

        # -----------------------------
        # Center Area (Canvas)
        # -----------------------------
        center_container = QFrame()
        center_container.setStyleSheet("background-color: #1E222A; border-radius: 8px;")
        center_container.setMinimumWidth(900)

        canvas_layout = QVBoxLayout()
        center_container.setLayout(canvas_layout)

        # Draggable table cards
        self.table_area = QWidget()
        self.table_area.setFixedSize(1400, 800)
        self.table_area.setStyleSheet("background-color: #1E222A;")
        self.table_area_layout = QVBoxLayout(self.table_area)

        # Add example draggable table cards
        card1 = TableCard("Table 1", ["Id", "Field_1", "Field_2"])
        card1.move(150, 150)
        card1.setParent(self.table_area)

        card2 = TableCard("Table 2", ["Id", "Field_1", "Field_2", "Table1_fk"])
        card2.move(450, 260)
        card2.setParent(self.table_area)

        card3 = TableCard("Table 3", ["Id", "Field_1", "Field_2", "Table2_fk"])
        card3.move(750, 120)
        card3.setParent(self.table_area)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        canvas_layout.addWidget(canvas_scroll)

        # -----------------------------
        # Right SQL Builder Panel
        # -----------------------------
        sql_panel = QVBoxLayout()
        lbl_sql = QLabel("SQL Query Builder")
        lbl_sql.setStyleSheet("font-size: 18px; color: white; font-weight: bold;")
        sql_panel.addWidget(lbl_sql)

        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #11141A;
                color: white;
                font-size: 14px;
                border-radius: 8px;
            }
        """)
        self.sql_editor.setPlaceholderText("Click on table fields to build your query...")
        self.sql_editor.setFixedWidth(360)
        sql_panel.addWidget(self.sql_editor)

        sql_panel.addStretch()

        # Add all panels to main layout
        main_layout.addLayout(sidebar)
        main_layout.addWidget(center_container)
        main_layout.addLayout(sql_panel)

