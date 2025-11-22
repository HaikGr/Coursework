from PyQt6.QtWidgets import (
    QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit,
    QScrollArea, QFrame, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, QSize


# ---------------------------
# Draggable Table Card Widget
# ---------------------------
class TableCard(QFrame):
    """A draggable card representing a database table."""
    def __init__(self, table_name, fields):
        super().__init__()
        self.table_name = table_name
        self.fields = fields
        # Adjusted size slightly for better fit
        self.setFixedSize(220, 180) 

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
        layout.setContentsMargins(15, 10, 10, 10)
        
        # Table Name Title
        title = QLabel(table_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title)
        
        # Field list
        for f in fields:
            # Use small dot as list marker
            lbl = QLabel(f"\u2022 {f}") 
            lbl.setStyleSheet("color: #C6C6C6; font-size: 13px;")
            layout.addWidget(lbl)

        layout.addStretch()
        self.setLayout(layout)

        self.drag_pos = None

    # Dragging implementation
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # store offset between mouse global position and widget position
            self.drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            # Calculate new position
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            # Move the widget
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

# ---------------------------
# Dashboard Window
# ---------------------------
class DashboardWindow(QMainWindow):
    """
    The main application interface, including the sidebar, canvas, and query builder.
    """
    def __init__(self, username, parent_window, geometry):
        super().__init__()
        self.setWindowTitle("Database Dashboard - Connected")
        self.restoreGeometry(geometry)
        self.setStyleSheet("background-color: #1C1F26;") # Dark background for the whole window
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
        top_line_layout.setContentsMargins(15, 0, 15, 0) # Added margins for content padding

        title = QLabel("Database Management System")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        top_line_layout.addWidget(title)
        top_line_layout.addStretch()

        # database info on the right
        db_info = QLabel(f"Connected User: {self.username}")
        db_info.setStyleSheet("color: white; font-size: 14px;")
        top_line_layout.addWidget(db_info)

        # Add top line to root layout
        root_layout.addWidget(top_line)

        # Sidebar | center and toolbar layout
        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0) # FIX: Removed unwanted vertical padding at the top of the sidebar
        root_layout.addLayout(body_layout)
        root_layout.setSpacing(0)

        # -----------------------------
        # Left Sidebar
        # -----------------------------

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0) # Set top margin to 0 for flush alignment
        sidebar_layout.setSpacing(0)
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setFixedWidth(240)
        # Style the sidebar to match the image's light background
        sidebar_widget.setStyleSheet("background-color: #FFFFFF;") 

        # Databases Text Golden Header
        databases_text = QFrame()
        databases_text.setFixedHeight(40)
        databases_text.setStyleSheet("""
            QFrame {
                background-color: #fbc840; /* Golden color */
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        databases_text_layout = QHBoxLayout(databases_text)
        databases_text_layout.setContentsMargins(15, 0, 0, 0)

        title = QLabel("Databases")
        title.setStyleSheet("color: #9b5120; font-size: 18px; font-weight: 600;")
        databases_text_layout.addWidget(title)
        databases_text_layout.addStretch()

        # Main Databases Tree Widget
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        # REMOVED: self.db_tree.setFixedHeight(500) -> allows it to stretch and fill space
        
        # New QSS to match the light theme and clean look from the image
        self.db_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #FFFFFF;
                color: #333333;
                border: none;
                padding-top: 5px;
                padding-bottom: 5px;
                outline: none;
            }

            QTreeWidget::item {
                height: 32px;
                padding-left: 10px;
                padding-top: 2px;
                padding-bottom: 2px;
            }

            QTreeWidget::item:hover {
                background-color: #F0F4F8; /* Subtle light hover */
            }

            QTreeWidget::item:selected {
                background-color: #E2ECFF; /* Light blue selection */
                color: #1C1F26;
                border-left: 3px solid #3777f0; /* Blue vertical bar on selection */
            }

            /* Styling for the Add Table link */
            QTreeWidget::item:hover:!selected[text(0)="+ Add Table"],
            QTreeWidget::item:!selected[text(0)="+ Add Table"] {
                color: #3777f0; /* Blue link color */
                font-style: italic;
                font-size: 13px;
                padding-left: 18px; /* Extra indent for table children */
            }

            /* Remove default triangles to match the clean visual style */
            QTreeWidget::branch:closed:has-children,
            QTreeWidget::branch:open:has-children {
                image: none;
                border-image: none;
            }
        """)
            
        # Data population function
        def add_database(name, tables):
            db_item = QTreeWidgetItem([name])
            db_item.setExpanded(True) # Start expanded for better visibility
            db_item.setData(0, Qt.ItemDataRole.UserRole, "database")
            self.db_tree.addTopLevelItem(db_item)

            # add tables
            for t in tables:
                table_item = QTreeWidgetItem([t])
                table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
                db_item.addChild(table_item)

            # add "+ Add Table"
            add_item = QTreeWidgetItem(["+ Add Table"])
            add_item.setData(0, Qt.ItemDataRole.UserRole, "add_table")
            db_item.addChild(add_item)

        add_database("Database 1", ["Table1", "Table2", "Table3"])
        add_database("Database 2", ["Table A", "Table B"])
        
        # Add a "+ New Database" button below the tree
        new_db_button = QPushButton("+ New Database")
        new_db_button.setStyleSheet("""
            QPushButton {
                background-color: #F0F4F8;
                color: #4A5668;
                font-size: 14px;
                font-weight: 500;
                border-radius: 6px;
                padding: 8px;
                margin: 10px;
                border: 1px dashed #C6C6C6;
            }
            QPushButton:hover {
                background-color: #E2ECFF;
                border: 1px dashed #3777f0;
            }
        """)
        
        # Log Out Button
        logout_button = QPushButton("LOG OUT")
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #E34A4A;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
                margin: 0px 10px 10px 10px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #D33A3A;
            }
        """)
        logout_button.clicked.connect(self.log_out)
        
        # Add elements to sidebar layout
        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree)
        sidebar_layout.addStretch(1) # Stretch to push buttons to the bottom
        sidebar_layout.addWidget(new_db_button) 
        sidebar_layout.addWidget(logout_button) 

        # Connect click handler
        def on_tree_click(item, col):
            role = item.data(0, Qt.ItemDataRole.UserRole)
            if role == "add_table":
                parent = item.parent()
                if parent:
                    # Logic to find a unique name and add a new table item
                    new_name = f"Table_{parent.childCount()}"
                    new_table_item = QTreeWidgetItem([new_name])
                    new_table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
                    # Insert above the "+ Add Table" entry
                    parent.insertChild(parent.childCount() - 1, new_table_item)
                    print(f"Created new table in {parent.text(0)}: {new_name}")
            elif role == "table":
                print(f"Table clicked: {item.text(0)}")


        self.db_tree.itemClicked.connect(on_tree_click)
        body_layout.addWidget(sidebar_widget)

        #########################################################################################

        # Center Area (Canvas)
        center_container = QFrame()
        center_container.setStyleSheet("background-color: #f5f6f7;")
        center_container.setMinimumWidth(900)

        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0) # Removed spacing between toolbar and canvas

        # Toolbar Frame (Light Gray in the image)
        toolbar_line = QFrame()
        toolbar_line.setFixedHeight(40)
        toolbar_line.setStyleSheet("""
            QFrame {
                background-color: #eeeff1;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        # Add mock buttons to the toolbar for appearance
        toolbar_layout = QHBoxLayout(toolbar_line)
        toolbar_layout.setContentsMargins(15, 0, 15, 0)
        toolbar_layout.addWidget(QPushButton("New"))
        toolbar_layout.addWidget(QPushButton("Open"))
        toolbar_layout.addWidget(QPushButton("Save"))
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QPushButton("RUN QUERY"))
        
        canvas_layout.addWidget(toolbar_line)
        
        # Draggable table cards area (a widget inside a scroll area)
        self.table_area = QWidget()
        self.table_area.setMinimumSize(1400, 900) # Large virtual canvas size
        self.table_area.setStyleSheet("background-color: #f5f6f7;")
        # no layout for absolute positioning of cards - we just parent the cards directly to the area

        # Add example draggable table cards (absolute positioned)
        card1 = TableCard("Users", ["user_id (PK)", "username", "email", "created_at"])
        card1.move(120, 80)
        card1.setParent(self.table_area)

        card2 = TableCard("Orders", ["order_id (PK)", "user_fk", "order_date", "total_amount"])
        card2.move(420, 220)
        card2.setParent(self.table_area)

        card3 = TableCard("Products", ["product_id (PK)", "name", "price", "category"])
        card3.move(760, 120)
        card3.setParent(self.table_area)

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.table_area)
        canvas_scroll.setStyleSheet("border: none;")
        canvas_layout.addWidget(canvas_scroll)

        center_container.setLayout(canvas_layout)
        body_layout.addWidget(center_container, stretch=3)

        # -----------------------------
        # Right SQL Builder Panel
        # -----------------------------

        sql_widget = QWidget()
        sql_layout = QVBoxLayout()
        sql_layout.setContentsMargins(0, 0, 0, 0)
        sql_layout.setSpacing(0)
        sql_widget.setLayout(sql_layout)
        sql_widget.setFixedWidth(300)
        
        # SQL Header (Blue)
        sql_header = QFrame()
        sql_header.setFixedHeight(40)
        sql_header.setStyleSheet("background-color: #3777f0;")
        sql_header_layout = QHBoxLayout(sql_header)
        sql_header_layout.setContentsMargins(15, 0, 15, 0)
        
        lbl_sql = QLabel("SQL Query Builder")
        lbl_sql.setStyleSheet("font-size: 16px; color: white; font-weight: 500;")
        sql_header_layout.addWidget(lbl_sql)
        sql_header_layout.addStretch()
        
        sql_layout.addWidget(sql_header)

        # SQL Editor Area
        editor_area = QWidget()
        editor_area_layout = QVBoxLayout(editor_area)
        editor_area_layout.setContentsMargins(10, 10, 10, 10)
        editor_area_layout.setSpacing(8)
        editor_area.setStyleSheet("background-color: #1C1F26;")


        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                background-color: #11192c;
                color: #E0E0E0;
                font-family: monospace;
                font-size: 14px;
                border-radius: 8px;
                padding: 10px;
                border: 1px solid #4A4F55;
            }
        """)
        self.sql_editor.setPlaceholderText("Click on table fields to build your query...")
        editor_area_layout.addWidget(self.sql_editor)

        editor_area_layout.addStretch()
        sql_layout.addWidget(editor_area)
        
        body_layout.addWidget(sql_widget, stretch=1)

    def log_out(self):
        """Log Outs and go back to main menu"""
        if self.parent_window:
            self.parent_window.show()
        self.close()
