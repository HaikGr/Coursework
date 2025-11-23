# dashboard.py
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea,
    QFrame, QTreeWidget, QTreeWidgetItem,
    QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
import sys

# ---------------------------
# Draggable Table Card Widget
# ---------------------------
class TableCard(QFrame):
    """A draggable card representing a database table."""
    def __init__(self, table_name, fields):
        super().__init__()
        self.table_name = table_name
        self.fields = fields
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

        title = QLabel(table_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        for f in fields:
            lbl = QLabel(f"\u2022 {f}")
            lbl.setStyleSheet("color: #C6C6C6; font-size: 13px;")
            layout.addWidget(lbl)

        layout.addStretch()
        self.setLayout(layout)
        self.drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

# Top Bar
class TopBar(QFrame):
    def __init__(self, username):
        super().__init__()
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #3777f0;")
        top_line_layout = QHBoxLayout(self)
        top_line_layout.setContentsMargins(15, 0, 15, 0)
        title = QLabel("Database Management System")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        top_line_layout.addWidget(title)
        top_line_layout.addStretch()
        db_info = QLabel(f"Connected User: {username}")
        db_info.setStyleSheet("color: white; font-size: 14px;")
        top_line_layout.addWidget(db_info)

# ---------------------------
# Left Sidebar (UI only)
# ---------------------------
class SideBar(QWidget):
    def __init__(self):
        super().__init__()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.setLayout(sidebar_layout)
        self.setFixedWidth(240)
        self.setStyleSheet("background-color: #FFFFFF;")

        databases_text = QFrame()
        databases_text.setFixedHeight(40)
        databases_text.setStyleSheet("background-color: #fbc840; border-bottom: 1px solid #E0E0E0;")
        dt_layout = QHBoxLayout(databases_text)
        dt_layout.setContentsMargins(15, 0, 0, 0)
        lbl_db = QLabel("Databases")
        lbl_db.setStyleSheet("color: #9b5120; font-size: 18px; font-weight: 600;")
        dt_layout.addWidget(lbl_db)
        dt_layout.addStretch()

        # expose db_tree as a public attribute so the main window can connect to it
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setFixedHeight(500)
        self.db_tree.setStyleSheet("""
            QTreeView::branch { background: transparent; }
            QTreeWidget { background-color: #FFFFFF; color: #333333; border: none; padding-top: 5px; padding-bottom: 5px; outline: none; }
            QTreeWidget::item { height: 40px; border-radius: 13px; padding-left: 30px; padding-top: 2px; padding-bottom: 2px; }
            QTreeWidget::item:hover { background-color: #F0F4F8; }
            QTreeWidget::item:selected { background-color: #2a6bee; color: white; }
            QTreeWidget::item[role="table"]:selected { background-color: #2a6bee; color: #fbc538; font-size: 14px; }
        """)

        def add_database(name, tables):
            db_item = QTreeWidgetItem([name])
            db_item.setExpanded(True)
            db_item.setData(0, Qt.ItemDataRole.UserRole, "database")
            self.db_tree.addTopLevelItem(db_item)
            for t in tables:
                table_item = QTreeWidgetItem([t])
                table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
                db_item.addChild(table_item)
            add_item = QTreeWidgetItem(["+ Add Table"])
            add_item.setData(0, Qt.ItemDataRole.UserRole, "add_table")
            db_item.addChild(add_item)

        add_database("Database 1", ["Table1", "Table2", "Table3"])
        add_database("Database 2", ["Table A", "Table B"])

        new_db_button = QPushButton("+ New Database")
        new_db_button.setStyleSheet("""
            QPushButton { background-color: #F0F4F8; color: #4A5668; font-size: 14px; font-weight: 500; border-radius: 6px; padding: 8px; margin: 10px; border: 1px dashed #C6C6C6; }
            QPushButton:hover { background-color: #E2ECFF; border: 1px dashed #3777f0; }
        """)

        logout_button = QPushButton("LOG OUT")
        logout_button.setStyleSheet("""
            QPushButton { background-color: #E34A4A; color: white; font-size: 16px; font-weight: bold; border-radius: 8px; padding: 10px; margin: 0px 10px 10px 10px; min-height: 40px; }
            QPushButton:hover { background-color: #D33A3A; }
        """)
        # don't call parent window logic here; DashboardWindow will connect signals

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree)
        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(new_db_button)
        sidebar_layout.addWidget(logout_button)

# ---------------------------
# SQL Query Builder (right panel)
# ---------------------------
class SQLQuerryBuilder(QWidget):
    def __init__(self):
        super().__init__()
        sql_layout = QVBoxLayout()
        sql_layout.setContentsMargins(0, 0, 0, 0)
        sql_layout.setSpacing(0)
        self.setLayout(sql_layout)
        self.setFixedWidth(300)

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

# ---------------------------
# Toolbar Frame (reusable)
# ---------------------------
class Toolbar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #eeeff1; border-bottom: 1px solid #E0E0E0;")
        toolbar_layout = QHBoxLayout(self)
        toolbar_layout.setContentsMargins(12, 0, 12, 0)
        toolbar_layout.addWidget(QPushButton("New"))
        toolbar_layout.addWidget(QPushButton("Open"))
        toolbar_layout.addWidget(QPushButton("Save"))
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QPushButton("Run Query"))

# ---------------------------
# Table Details Page
# ---------------------------
class TableDetailsPage(QWidget):
    """A page that shows schema and records for a selected table."""
    def __init__(self, table_name, columns, rows):
        super().__init__()
        self.table_name = table_name
        self.columns = columns
        self.rows = rows

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        toolbar = Toolbar()
        layout.addWidget(toolbar)

        header = QLabel(f"Table: {table_name}")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)

        # Schema area (simple labels)
        schema_frame = QFrame()
        sf_layout = QVBoxLayout(schema_frame)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.addWidget(QLabel("Schema:"))
        for c in columns:
            lbl = QLabel(f"• {c}")
            lbl.setStyleSheet("color: #333333;")
            sf_layout.addWidget(lbl)
        layout.addWidget(schema_frame)

        # Records table
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        for r_idx, r in enumerate(rows):
            for c_idx, value in enumerate(r):
                table.setItem(r_idx, c_idx, QTableWidgetItem(str(value)))

        layout.addWidget(table)

# ---------------------------
# Diagram Page (draggable cards)
# ---------------------------
class DiagramPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # toolbar placeholder
        toolbar = Toolbar()
        layout.addWidget(toolbar)

        # canvas area (scrollable) for draggable cards
        self.table_area = QWidget()
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")
        # Add example cards
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
        layout.addWidget(canvas_scroll)

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
        self.setStyleSheet("background-color: #1C1F26;")
        self.parent_window = parent_window
        self.username = username

        # store pages map here
        self.page_map = {}
        main_widget = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        main_widget.setLayout(root_layout)
        self.setCentralWidget(main_widget)

        # Top bar
        top_line = TopBar(username)
        root_layout.addWidget(top_line)

        # Body layout: left sidebar, center stacked, right SQL builder
        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(body_layout)
        root_layout.setSpacing(0)

        # -----------------------------
        # Left Sidebar (UI only)
        # -----------------------------
        self.sidebar_widget = SideBar()
        body_layout.addWidget(self.sidebar_widget)

        # -----------------------------
        # Center StackedWidget
        # -----------------------------
        self.stacked_center = QStackedWidget()
        self.stacked_center.setMinimumWidth(900)

        # Create pages
        self.diagram_page = DiagramPage()
        self.stacked_center.addWidget(self.diagram_page)  # index 0 is diagram

        # Add a simple Add Table page (used only briefly if needed)
        add_table_page = QWidget()
        at_layout = QVBoxLayout(add_table_page)
        at_layout.addWidget(QLabel("New table created. Click the tree to open its page."))
        self.stacked_center.addWidget(add_table_page)
        self.add_table_page_index = self.stacked_center.indexOf(add_table_page)

        body_layout.addWidget(self.stacked_center, stretch=3)

        # -----------------------------
        # Right SQL Builder Panel (always visible)
        # -----------------------------
        sql_widget = SQLQuerryBuilder()
        body_layout.addWidget(sql_widget, stretch=1)

        # -----------------------------
        # Connect the sidebar tree to a handler here (in DashboardWindow)
        # -----------------------------
        self.sidebar_widget.db_tree.itemClicked.connect(self.on_tree_click)

    # create_table_page belongs to DashboardWindow (so it can access stacked widget)
    def create_table_page(self, table_name, columns, rows):
        """Create a TableDetailsPage for a table and register it in the stacked widget."""
        page = TableDetailsPage(table_name, columns, rows)
        idx = self.stacked_center.addWidget(page)
        self.page_map[table_name] = (page, idx)
        return idx

    # handler lives in DashboardWindow so it can manipulate the stacked widget
    def on_tree_click(self, item, col):
        role = item.data(0, Qt.ItemDataRole.UserRole)
        if role == "add_table":
            parent = item.parent()
            if parent:
                # create a unique table name
                base = "NewTable"
                idx = 1
                new_name = f"{base}{idx}"
                # ensure uniqueness under this db
                existing = {parent.child(i).text(0) for i in range(parent.childCount())}
                while new_name in existing:
                    idx += 1
                    new_name = f"{base}{idx}"
                new_table_item = QTreeWidgetItem([new_name])
                new_table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
                parent.insertChild(parent.childCount() - 1, new_table_item)
                # create a page for it (empty schema/data to start)
                self.create_table_page(new_name, ["id (int)"], [[1]])
                # show the new table page
                page_index = self.page_map[new_name][1]
                self.stacked_center.setCurrentIndex(page_index)
                print(f"Created new table in {parent.text(0)}: {new_name}")
        elif role == "table":
            table_name = item.text(0)
            # show or create table page
            if table_name not in self.page_map:
                # Create a new page with some placeholder schema & rows.
                columns = ["Id", "Field_1", "Field_2"]
                rows = [
                    [1, "Gasparyan", "$200000"],
                    [2, "Tagavor", "$300000"],
                    [3, "Bryan", "$250000"],
                    [4, "Unknown", "$0"]
                ]
                self.create_table_page(table_name, columns, rows)
            page_index = self.page_map[table_name][1]
            self.stacked_center.setCurrentIndex(page_index)
            print(f"Table clicked: {table_name}")

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
