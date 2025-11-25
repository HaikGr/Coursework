from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton,
    QFrame, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import (
    Qt
)

from items.TableDetailsPage import TableDetailsPage


class SideBar(QWidget):
    def __init__(self, stack_widget):
        super().__init__()
        self.stacked_center = stack_widget
        self.page_map = {}
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

        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setFixedHeight(500)
        self.db_tree.setStyleSheet("""
            QTreeView::branch { background: transparent; }
            QTreeWidget { background-color: #FFFFFF; color: #333333; border: none; padding-top: 5px; padding-bottom: 5px; outline: none; }
            QTreeWidget::item { height: 40px; border-radius: 13px; padding-left: 30px; padding-top: 2px; padding-bottom: 2px; }
            QTreeWidget::item:hover { background-color: #F0F4F8; }
            QTreeWidget::item:selected { background-color: #2a6bee; color: white; }
        """)
        self.db_tree.itemClicked.connect(self.on_tree_click)

        def add_database(name):
            db_item = QTreeWidgetItem([name])
            db_item.setExpanded(True)
            db_item.setData(0, Qt.ItemDataRole.UserRole, "database")
            self.db_tree.addTopLevelItem(db_item)
            add_item = QTreeWidgetItem(["+ Add Table"])
            add_item.setData(0, Qt.ItemDataRole.UserRole, "add_table")
            db_item.addChild(add_item)

        add_database("Database 1")

        new_db_button = QPushButton("+ New Database")
        new_db_button.setStyleSheet("""
            QPushButton { background-color: #F0F4F8; color: #4A5668; font-size: 14px; font-weight: 500; border-radius: 6px; padding: 8px; margin: 10px; border: 1px dashed #C6C6C6; }
            QPushButton:hover { background-color: #E2ECFF; border: 1px dashed #3777f0; }
        """)
        new_db_button.clicked.connect(add_database)

        logout_button = QPushButton("LOG OUT")
        logout_button.setStyleSheet("""
            QPushButton { background-color: #E34A4A; color: white; font-size: 16px; font-weight: bold; border-radius: 8px; padding: 10px; margin: 0px 10px 10px 10px; min-height: 40px; }
            QPushButton:hover { background-color: #D33A3A; }
        """)

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree)
        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(new_db_button)
        sidebar_layout.addWidget(logout_button)

    def create_table_page(self, table_name):
        page = TableDetailsPage(table_name, self.stacked_center)
        diagram_page = self.stacked_center.widget(0)
        
        page.table_data_ready.connect(diagram_page.add_table_card)
        page.field_deleted.connect(diagram_page.remove_field_from_card)
        idx = self.stacked_center.addWidget(page)
        self.page_map[table_name] = (page, idx)
        return idx

    def on_tree_click(self, item):
        role = item.data(0, Qt.ItemDataRole.UserRole)
        if role == "add_table":
            parent = item.parent()
            if parent:
                base = "NewTable"
                idx = 1
                new_name = f"{base}{idx}"
                existing = {parent.child(i).text(0) for i in range(parent.childCount())}
                while new_name in existing:
                    idx += 1
                    new_name = f"{base}{idx}"
                new_table_item = QTreeWidgetItem([new_name])
                new_table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
                parent.insertChild(parent.childCount() - 1, new_table_item)
                self.create_table_page(new_name)
                page_index = self.page_map[new_name][1]
                self.stacked_center.setCurrentIndex(page_index)
                print(f"Created new table in {parent.text(0)}: {new_name}")
        elif role == "table":
            table_name = item.text(0)
            if table_name not in self.page_map:
                self.create_table_page(table_name)
            page_index = self.page_map[table_name][1]
            self.stacked_center.setCurrentIndex(page_index)