import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel,
    QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

# --- Main Application Window ---

class DatabaseApp(QMainWindow):
    """
    Main application window replicating the Database Management System UI.
    Uses QSS for dark theme styling and various layout containers (H/VBoxLayout, QSplitter).
    """
    def init(self):
        super().init()
        self.setWindowTitle("Database Management System")
        # Set a large initial geometry to match a desktop application view
        self.setGeometry(100, 100, 1400, 800)
        
        self.apply_styles()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # The main layout is a QVBoxLayout to stack the Header and the Content Area
        full_layout = QVBoxLayout(central_widget)
        full_layout.setSpacing(0)
        full_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Top Header Bar
        self.create_header_bar()
        full_layout.addWidget(self.header_widget)

        # 2. Main Content Area (Split into 3 vertical panels: Left, Center, Right)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self.create_left_panel())
        content_splitter.addWidget(self.create_central_area())
        content_splitter.addWidget(self.create_right_panel())
        
        # Adjust initial sizes (Left: ~18%, Center: ~57%, Right: ~25%)
        total_size = 1400 # approx width
        content_splitter.setSizes([int(total_size*0.18), int(total_size*0.57), int(total_size*0.25)])
        
        full_layout.addWidget(content_splitter)

    def create_header_bar(self):
        """Creates the fixed top header bar with action buttons and the RUN QUERY button."""
        self.header_widget = QWidget()
        self.header_widget.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(15, 5, 15, 5)
        header_layout.setSpacing(10)
        
        # Left Logo/Title
        title_label = QLabel("Database Management System")
        title_label.setObjectName("HeaderTitle")
        title_label.setFont(QFont("Segoe UI", 16))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch(1) # Push content to the right

        # Mid-Section: File Actions
        actions = [("New", "file-o"), ("Open", "folder-open-o"), ("Save", "save"), ("AGGREGATE FUNCTIONS", None)]
        for text, icon_name in actions:
            btn = QPushButton(text)
            btn.setObjectName("HeaderButton")
            header_layout.addWidget(btn)

        # Mid-Section: Function buttons (SUM, AVG, COUNT, etc.)
        func_container = QWidget()
        func_container.setObjectName("FuncContainer")
        func_layout = QHBoxLayout(func_container)
        func_layout.setContentsMargins(0, 0, 0, 0)
        func_layout.setSpacing(1)
        for text in ["SUM", "AVG", "COUNT", "MIN", "MAX"]:
            btn = QPushButton(text)
            btn.setObjectName("FuncButton")
            func_layout.addWidget(btn)
        header_layout.addWidget(func_container)
        
        # Right Search/Run Query/DB Dropdown
        # Using text placeholders for icons for simplicity
        for _ in range(5):
            icon_label = QLabel("🔍") 
            icon_label.setObjectName("HeaderIconPlaceholder")
            header_layout.addWidget(icon_label)
        
        run_query_btn = QPushButton("RUN QUERY")
        run_query_btn.setObjectName("RunQueryButton")
        run_query_btn.setFixedSize(120, 35)
        header_layout.addWidget(run_query_btn)
        
        db_dropdown = QPushButton("Database 1 🔽")
        db_dropdown.setObjectName("HeaderDropdown")
        header_layout.addWidget(db_dropdown)

    def create_left_panel(self):
            """Creates the left navigation panel (Databases Tree and Log Out button)."""
            left_panel = QWidget()
            left_panel.setObjectName("LeftPanel")
            v_layout = QVBoxLayout(left_panel)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(0)
            
            # Databases Label
            db_label = QLabel("Databases")
            db_label.setObjectName("PanelLabel")
            db_label.setFixedHeight(40)
            db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            db_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            v_layout.addWidget(db_label)
            
            # Database 1 Group (Selected)
            db1_group = QWidget()
            db1_group.setObjectName("DatabaseGroup")
            db1_layout_outer = QVBoxLayout(db1_group)
            db1_layout_outer.setContentsMargins(0, 0, 0, 0)
            
            db1_header = QPushButton("Database 1 🔽")
            db1_header.setObjectName("DatabaseHeaderSelected")
            db1_header.setFixedHeight(40)
            db1_layout_outer.addWidget(db1_header)
            
            # Table List (Simulating nested structure)
            tables_list_widget = QListWidget()
            tables_list_widget.setObjectName("TablesList")
            
            # Table1 (Active - using custom widget for coloring)
            item1 = QListWidgetItem()
            widget1 = QWidget()
            h_layout1 = QHBoxLayout(widget1)
            h_layout1.setContentsMargins(10, 5, 10, 5)
            label1 = QLabel("Table1")
            label1.setObjectName("TableNameLabelSelected")
            h_layout1.addWidget(label1)
            h_layout1.addStretch(1)
            item1.setSizeHint(widget1.sizeHint())
            tables_list_widget.addItem(item1)
            tables_list_widget.setItemWidget(item1, widget1)
            
            # Other tables
            for name in ["Table2", "Table3"]:
                item = QListWidgetItem(name)
                item.setFlags(Qt.ItemFlag.NoFocus | Qt.ItemFlag.ItemIsEnabled)
                tables_list_widget.addItem(item)
                
            add_table_btn = QPushButton("+ Add Table")
            add_table_btn.setObjectName("AddButton")
            add_table_btn.setMinimumHeight(30)
            
            db1_layout_tables = QVBoxLayout()
            db1_layout_tables.setContentsMargins(10, 0, 10, 0)
            db1_layout_tables.addWidget(tables_list_widget)
            db1_layout_tables.addWidget(add_table_btn)
            db1_layout_outer.addLayout(db1_layout_tables)
            
            v_layout.addWidget(db1_group)

            # Database 2 Header
            db2_header = QPushButton("Database 2 ᐅ")
            db2_header.setObjectName("DatabaseHeader")
            db2_header.setFixedHeight(40)
            v_layout.addWidget(db2_header)
            
            # New Database Button
            new_db_btn = QPushButton("+ New Database")
            new_db_btn.setObjectName("AddButton")
            new_db_btn.setMinimumHeight(40)
            v_layout.addWidget(new_db_btn)
            
            v_layout.addStretch(1) # Push Log Out to the bottom
            
            # Log Out Button
            logout_btn = QPushButton("LOG OUT")
            logout_btn.setObjectName("LogoutButton")
            logout_btn.setMinimumHeight(50)
            v_layout.addWidget(logout_btn)
            
            return left_panel

    def create_central_area(self):
        """Creates the main working area, split into Schema and Data Records panels."""
        central_area = QWidget()
        central_area.setObjectName("CentralArea")
        v_layout = QVBoxLayout(central_area)
        v_layout.setContentsMargins(15, 10, 15, 10)
        v_layout.setSpacing(15)

    # Top Toolbar (Back, Table1 Label, Icons)
        toolbar = QWidget()
        toolbar.setObjectName("CentralToolbar")
        h_layout = QHBoxLayout(toolbar)
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        h_layout.addWidget(QPushButton(" < Back "))
        h_layout.addWidget(QLabel("Table1"))
        h_layout.addStretch(1)
        
        for text in ["T", "S", "C"]:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.setObjectName("CentralToolbarButton")
            h_layout.addWidget(btn)
            
        v_layout.addWidget(toolbar)

        # Main Split Content (Schema/Records)
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Split: Schema View ---
        schema_panel = QWidget()
        schema_panel.setObjectName("SchemaPanel")
        v_schema_layout = QVBoxLayout(schema_panel)
        v_schema_layout.setContentsMargins(10, 10, 10, 10)
        v_schema_layout.setSpacing(5)

        # Schema Header (Yellow)
        schema_label = QLabel("Schema")
        schema_label.setObjectName("SchemaHeader")
        schema_label.setFixedHeight(30)
        v_schema_layout.addWidget(schema_label)
        
        # Schema Table (Using QTableWidget for schema fields)
        schema_table = QTableWidget(4, 3) 
        schema_table.setHorizontalHeaderLabels(["Column", "Type", "Null"])
        schema_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        schema_table.verticalHeader().setVisible(False)
        schema_table.setObjectName("SchemaTable")
        
        # Placeholder data
        schema_table.setItem(0, 0, QTableWidgetItem("Id"))
        schema_table.setItem(0, 1, QTableWidgetItem("int"))
        schema_table.setItem(1, 0, QTableWidgetItem("Field_1"))
        schema_table.setItem(1, 1, QTableWidgetItem("nvarchar(20)"))
        schema_table.setItem(2, 0, QTableWidgetItem("Field_2"))
        schema_table.setItem(2, 1, QTableWidgetItem("money"))
        schema_table.setItem(3, 0, QTableWidgetItem("Unknown"))
        schema_table.setItem(3, 1, QTableWidgetItem("Unknown"))
        
        v_schema_layout.addWidget(schema_table)
        content_splitter.addWidget(schema_panel)

        # --- Right Split: Data Records View ---
        data_records_panel = QWidget()
        data_records_panel.setObjectName("DataRecordsPanel")
        v_records_layout = QVBoxLayout(data_records_panel)
        v_records_layout.setContentsMargins(10, 10, 10, 10)
        v_records_layout.setSpacing(5)
        
        # Data Records Header (Green)
        header_widget = QWidget()
        header_widget.setObjectName("DataRecordsHeaderContainer")
        h_header_layout = QHBoxLayout(header_widget)
        h_header_layout.setContentsMargins(10, 5, 10, 5)
        
        data_label = QLabel("Data Records")
        data_label.setObjectName("DataRecordsLabel")
        h_header_layout.addWidget(data_label)
        h_header_layout.addStretch(1)
        h_header_layout.addWidget(QLabel("4 rows")) 
        
        v_records_layout.addWidget(header_widget)
        
        # Data Records Table
        data_table = QTableWidget(4, 3)
        data_table.setHorizontalHeaderLabels(["Id", "Field_1", "Field_2"])
        data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        data_table.verticalHeader().setFixedWidth(20)
        data_table.setObjectName("DataTable")
        
        # Placeholder data
        data_table.setItem(0, 0, QTableWidgetItem("1"))
        data_table.setItem(0, 1, QTableWidgetItem("Gasparyan"))
        data_table.setItem(0, 2, QTableWidgetItem("$200000"))
        
        data_table.setItem(1, 0, QTableWidgetItem("7"))
        data_table.setItem(1, 1, QTableWidgetItem("Tagavor"))
        data_table.setItem(1, 2, QTableWidgetItem("$300000"))
        
        data_table.setItem(2, 0, QTableWidgetItem("8"))
        data_table.setItem(2, 1, QTableWidgetItem("Bryan"))
        data_table.setItem(2, 2, QTableWidgetItem("$250000"))

        data_table.setItem(3, 0, QTableWidgetItem("4"))
        data_table.setItem(3, 1, QTableWidgetItem("Unknown"))
        data_table.setItem(3, 2, QTableWidgetItem("$0"))
        
        v_records_layout.addWidget(data_table)
        content_splitter.addWidget(data_records_panel)

        # Set initial sizes for schema and records
        content_splitter.setSizes([int(700*0.4), int(700*0.6)])

        v_layout.addWidget(content_splitter)
        
        return central_area

    def create_right_panel(self):
        """Creates the right side panel (SQL Query Builder)."""
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        v_layout = QVBoxLayout(right_panel)
        v_layout.setContentsMargins(15, 10, 15, 10)
        
        # Header and Subtitle (Blue Themed)
        header = QLabel("SQL Query Builder")
        header.setObjectName("RightPanelHeader")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        v_layout.addWidget(header)
        
        subtitle = QLabel("Visual Query Construction")
        subtitle.setObjectName("RightPanelSubtitle")
        v_layout.addWidget(subtitle)
        
        v_layout.addSpacing(20)
        
        # Query Instructions Box
        instruction_box = QWidget()
        instruction_box.setObjectName("InstructionBox")
        instruction_layout = QVBoxLayout(instruction_box)
        instruction_layout.setContentsMargins(15, 15, 15, 15)
        
        instruction_label = QLabel("Click on table fields to build your query...")
        instruction_label.setWordWrap(True)
        instruction_layout.addWidget(instruction_label)
        instruction_layout.addStretch(1)
        
        v_layout.addWidget(instruction_box)
        v_layout.addStretch(1)
        
        return right_panel

    def apply_styles(self):
        """Applies a custom dark stylesheet using QSS."""
        style = """
        /* General Dark Theme */
        QMainWindow, QWidget, QSplitter {
            background-color: #2c323f; /* Dark Gray Background */
            color: #f0f0f0; /* Light Text */
            font-family: "Segoe UI", sans-serif;
            font-size: 10pt;
        }
        
        /* --- HEADER BAR --- */
        #HeaderBar {
            background-color: #3b4252; /* Slightly Lighter Dark Blue for Header */
        }
        #HeaderTitle {
            color: #f0f0f0;
            font-weight: bold;
        }
        
        /* General Header Buttons */
        QPushButton {
            border-radius: 5px;
            padding: 8px 12px;
            border: none;
            background-color: #4c566a;
            color: #f0f0f0;
        }
        QPushButton:hover {
            background-color: #5e697a;
        }
        
        /* Functional Buttons Group (SUM, AVG, etc.) */
        #FuncContainer {
            background-color: #4c566a;
            border-radius: 5px;
            padding: 0;
            border: 1px solid #5e697a;
        }
        #FuncButton {
            background-color: transparent;
            padding: 5px 10px;
        }
        
        /* RUN QUERY Button (Primary Green) */
        #RunQueryButton {
            background-color: #4caf50; /* Green */
            color: white;
            font-weight: bold;
        }
        #RunQueryButton:hover {
            background-color: #66bb6a;
        }
        
        /* --- LEFT PANEL (Databases) --- */
        #LeftPanel {
            background-color: #3b4252; /* Blue-Gray Sidebar */
            min-width: 250px;
            border-right: 1px solid #4c566a;
        }
        #PanelLabel {
            background-color: #2c323f;
        }
        
        /* Database Headers */
        #DatabaseHeader, #DatabaseHeaderSelected {
            border: none;
            text-align: left;
            padding-left: 20px;
        }
        #DatabaseHeaderSelected {
            background-color: #4c566a; /* Darker selection highlight */
            font-weight: bold;
        }
        
        /* Tables List */
        QListWidget {
            background-color: transparent;
            border: none;
            padding: 5px 0;
        }
        /* Table Name Label (for non-active tables) */
        QListWidget::item {
            color: #f0f0f0;
            padding: 5px 20px;
        }
        #TableNameLabelSelected {
            background-color: #3b4252; /* Selected Table background (matches parent for inset look) */
            border-radius: 5px;
            padding: 5px 10px;
            font-weight: bold;
            color: #ffc107; /* Yellow for text highlight */
        }
        
        /* Add Button */
        #AddButton {
            background-color: transparent;
            border: 1px dashed #5e697a;
            color: #a0a0a0;
            margin: 10px;
        }

        /* LOG OUT Button (Red) */
        #LogoutButton {
            background-color: #e53935; /* Red */
            color: white;
            font-weight: bold;
            margin: 10px;
        }

        /* --- CENTRAL AREA --- */
        #CentralArea {
            background-color: #3b4252;
        }
        
        /* Inner Panels (Schema/Data) */
        #SchemaPanel, #DataRecordsPanel {
            background-color: #4c566a; /* Medium dark panel color */
            border-radius: 10px;
            padding: 10px;
        }
        
        /* Schema Header (Yellow) */
        #SchemaHeader {
            background-color: #ffc107;
            color: #333;
            font-weight: bold;
            border-radius: 5px;
            padding: 5px 10px;
        }
        
        /* Data Records Header (Green) */
        #DataRecordsHeaderContainer {
            background-color: #4caf50; /* Green */
            border-radius: 5px;
            color: white;
            font-weight: bold;
            padding: 5px 10px;
        }
        
        /* Tables (General Style) */
        QTableWidget {
            gridline-color: #5e697a;
            border: 1px solid #5e697a;
            selection-background-color: #5e697a;
            border-radius: 5px;
        }
        QHeaderView::section {
            background-color: #3b4252; /* Darker header for tables */
            color: #f0f0f0;
            padding: 5px;
            border: 1px solid #5e697a;
        }
        
        /* --- RIGHT PANEL (Query Builder) --- */
        #RightPanel {
            background-color: #2c323f; /* Darkest background */
            border-left: 1px solid #4c566a;
            padding: 10px;
        }
        #RightPanelHeader {
            color: #00bfff; /* Bright Blue Accent */
        }
        #RightPanelSubtitle {
            font-size: 8pt;
            color: #a0a0a0;
        }
        
        #InstructionBox {
            background-color: #3b4252;
            border-radius: 5px;
            min-height: 100px;
            border: 1px solid #00bfff; /* Blue Border */
            padding: 10px;
        }
        #HeaderIconPlaceholder {
            padding: 0 5px;
        }
        """
        self.setStyleSheet(style)


if __name__ == '__main__':
    # Standard PySide6 application boilerplate
    app = QApplication(sys.argv)
    window = DatabaseApp()
    window.show()
    sys.exit(app.exec())