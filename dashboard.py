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
    def __init__(self, username, parent_window, geometry):
        super().__init__()
        self.setWindowTitle("Database Dashboard - Connected")
        self.restoreGeometry(geometry)
        self.setStyleSheet("background-color: #1C1F26;")
        self.parent_window = parent_window
        self.username = username

        # Central widget & root layout (vertical: top bar + body)
        main_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        main_widget.setLayout(root_layout)
        self.setCentralWidget(main_widget)

        # -----------------------------
        # Top Blue Horizontal Bar
        # -----------------------------

        top_line = QFrame()
        top_line.setFixedHeight(40)
        top_line.setStyleSheet("""
            QFrame {
                background-color: #3777f0;
            }
        """)
        top_line_layout = QHBoxLayout(top_line)

        title = QLabel("Database Management System")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        top_line_layout.addWidget(title)
        top_line_layout.addStretch()

        # database info on the right
        db_info = QLabel(f"Database: 1 {self.username}")
        db_info.setStyleSheet("color: white; font-size: 14px;")
        top_line_layout.addWidget(db_info)

        # Add top line to root layout
        root_layout.addWidget(top_line)

        # -----------------------------
        # Body layout: sidebar | center | sql panel
        # -----------------------------

        # Sidebar | center and toolbar layout

        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        root_layout.addLayout(body_layout)
        root_layout.setSpacing(0)

        # -----------------------------
        # Left Sidebar
        # -----------------------------

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 10)
        sidebar_layout.setSpacing(0)
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setFixedWidth(240)
        sidebar_widget.setStyleSheet("background-color: transparent;") 

        databases_text = QFrame()
        databases_text.setFixedHeight(40)
        databases_text.setStyleSheet("""
            QFrame {
                background-color: #fbc840;
            }
        """)
        databases_text_layout = QHBoxLayout(databases_text)

        title = QLabel("Databases")
        title.setStyleSheet("color: #9b5120; font-size: 18px; font-weight: 600;")
        databases_text_layout.addWidget(title)
        databases_text_layout.addStretch()

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
        self.db_list.setFixedHeight(500)
        logout_button = QPushButton("LOG OUT")
        logout_button.setFixedSize(200, 60)
        logout_button.setStyleSheet(
            """
            QPushButton {
                background-color: #dd2828;
                color: white;
                font-size: 15px;
                border-radius: 15px;
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #7BA3D0;
            }
            """)
        logout_button.clicked.connect(self.log_out)
        
        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_list)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(logout_button, alignment=Qt.AlignmentFlag.AlignCenter)
        body_layout.addWidget(sidebar_widget)

        

        # Toolbar in the center
        toolbar_line = QFrame()
        toolbar_line.setFixedHeight(40)
        toolbar_line.setStyleSheet("""
            QFrame {
                background-color: #eeeff1;
            }
        """)

        # Add top line to root layout
        # -----------------------------
        # Center Area (Canvas)
        # -----------------------------
        
        center_container = QFrame()
        center_container.setStyleSheet("background-color: #f5f6f7;")
        center_container.setMinimumWidth(900)

        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(6)
        canvas_layout.addWidget(toolbar_line)
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

        body_layout.addWidget(center_container, stretch=3)

        # -----------------------------
        # Right SQL Builder Panel
        # -----------------------------

        sql_widget = QWidget()
        sql_layout = QVBoxLayout()
        sql_layout.setContentsMargins(10, 10, 10, 10)
        sql_layout.setSpacing(8)
        sql_widget.setLayout(sql_layout)
        sql_widget.setFixedWidth(300)

        lbl_sql = QLabel("SQL Query Builder")
        lbl_sql.setStyleSheet("font-size: 18px; color: white; font-weight: bold;")
        sql_layout.addWidget(lbl_sql)

        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #11192c;
                color: white;
                font-size: 14px;
                border-radius: 8px;
            }
        """)
        self.sql_editor.setPlaceholderText("Click on table fields to build your query...")
        self.sql_editor.setFixedWidth(280)
        sql_layout.addWidget(self.sql_editor)

        sql_layout.addStretch()
        body_layout.addWidget(sql_widget, stretch=1)

    def log_out(self):
        """Log Outs and go back to main menu"""
        if self.parent_window:
            self.parent_window.show()
        self.close()





