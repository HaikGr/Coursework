import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QTextEdit,
    QScrollArea, QFrame
)
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
            # store offset between mouse global position and widget position
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
    def __init__(self, username="User"):
        super().__init__()
        self.setWindowTitle("Database Dashboard - Connected")
        self.setGeometry(200, 100, 1600, 900)
        self.setStyleSheet("background-color: #1C1F26;")

        # Central widget & root layout (vertical: top bar + body)
        main_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        main_widget.setLayout(root_layout)
        self.setCentralWidget(main_widget)

        # -----------------------------
        # Top Blue Horizontal Bar
        # -----------------------------
        top_line = QFrame()
        top_line.setFixedHeight(56)
        top_line.setStyleSheet("""
            QFrame {
                background-color: #3777f0;
                border-radius: 8px;
            }
        """)
        top_line_layout = QHBoxLayout(top_line)
        top_line_layout.setContentsMargins(16, 6, 16, 6)
        # top_line_layout.setSpacing(10)

        title = QLabel("Database Management System")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        top_line_layout.addWidget(title)

        # optional small subtitle
        subtitle = QLabel("— SQL Designer")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px; margin-left:6px;")
        top_line_layout.addWidget(subtitle)

        top_line_layout.addStretch()

        # database info on the right
        db_info = QLabel("Database: demo_db (2)")
        db_info.setStyleSheet("color: white; font-size: 14px;")
        top_line_layout.addWidget(db_info)

        # Add top line to root layout
        root_layout.addWidget(top_line)

        # -----------------------------
        # Body layout: sidebar | center | sql panel
        # -----------------------------
        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)
        root_layout.addLayout(body_layout)

        # -----------------------------
        # Left Sidebar
        # -----------------------------
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(10)
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setFixedWidth(240)
        sidebar_widget.setStyleSheet("background-color: transparent;")  # parent background shows

        lbl_db = QLabel("Databases")
        lbl_db.setStyleSheet("font-size: 18px; color: white; font-weight: bold;")
        sidebar_layout.addWidget(lbl_db)

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
        self.db_list.addItem("Database 1")
        self.db_list.addItem("Database 2")
        self.db_list.setFixedWidth(220)
        sidebar_layout.addWidget(self.db_list)

        sidebar_layout.addStretch()
        body_layout.addWidget(sidebar_widget)

        # -----------------------------
        # Center Area (Canvas)
        # -----------------------------
        center_container = QFrame()
        center_container.setStyleSheet("background-color: #f5f6f7; border-radius: 8px;")
        center_container.setMinimumWidth(900)

        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setSpacing(6)
        center_container.setLayout(canvas_layout)

        # Draggable table cards area (a widget inside a scroll area)
        self.table_area = QWidget()
        # make a large virtual canvas size (scrollable)
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")
        # no layout for absolute positioning of cards
        self.table_area_layout = QVBoxLayout(self.table_area)
        self.table_area_layout.setContentsMargins(0, 0, 0, 0)

        # Add example draggable table cards (absolute positioned)
        card1 = TableCard("Table 1", ["Id", "Field_1", "Field_2"])
        card1.move(120, 80)
        card1.setParent(self.table_area)

        card2 = TableCard("Table 2", ["Id", "Field_1", "Field_2", "Table1_fk"])
        card2.move(420, 220)
        card2.setParent(self.table_area)

        card3 = TableCard("Table 3", ["Id", "Field_1", "Field_2", "Table2_fk"])
        card3.move(760, 120)
        card3.setParent(self.table_area)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        canvas_layout.addWidget(canvas_scroll)

        body_layout.addWidget(center_container, stretch=1)

        # -----------------------------
        # Right SQL Builder Panel
        # -----------------------------
        sql_widget = QWidget()
        sql_layout = QVBoxLayout()
        sql_layout.setContentsMargins(8, 8, 8, 8)
        sql_layout.setSpacing(8)
        sql_widget.setLayout(sql_layout)
        sql_widget.setFixedWidth(380)

        lbl_sql = QLabel("SQL Query Builder")
        lbl_sql.setStyleSheet("font-size: 18px; color: white; font-weight: bold;")
        sql_layout.addWidget(lbl_sql)

        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #162032;
                color: white;
                font-size: 14px;
                border-radius: 8px;
            }
        """)
        self.sql_editor.setPlaceholderText("Click on table fields to build your query...")
        self.sql_editor.setFixedWidth(360)
        sql_layout.addWidget(self.sql_editor)

        sql_layout.addStretch()
        body_layout.addWidget(sql_widget)

        # store widgets if needed
        self.top_line = top_line
        self.center_container = center_container
        self.sidebar_widget = sidebar_widget
        self.sql_widget = sql_widget



