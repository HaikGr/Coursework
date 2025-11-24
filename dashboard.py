# dashboard.py
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidgetItem, QStackedWidget
)
from PyQt6.QtCore import (
    Qt
)
import sys

from items.TopBar import TopBar
from items.SideBar import SideBar
from items.DiagramPage import DiagramPage
from items.SQLQuerryBuilder import SQLQuerryBuilder
from items.TableDetailsPage import TableDetailsPage


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

        self.page_map = {}
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

        self.sidebar_widget = SideBar()
        body_layout.addWidget(self.sidebar_widget)

        self.stacked_center = QStackedWidget()
        self.stacked_center.setMinimumWidth(900)

        self.diagram_page = DiagramPage()
        self.stacked_center.addWidget(self.diagram_page)

        add_table_page = QWidget()
        self.stacked_center.addWidget(add_table_page)
        self.add_table_page_index = self.stacked_center.indexOf(add_table_page)

        body_layout.addWidget(self.stacked_center, stretch=3)

        sql_widget = SQLQuerryBuilder()
        body_layout.addWidget(sql_widget, stretch=1)

        self.sidebar_widget.db_tree.itemClicked.connect(self.on_tree_click)

    def create_table_page(self, table_name, columns, rows):
        page = TableDetailsPage(table_name, columns, rows, self.stacked_center)
        idx = self.stacked_center.addWidget(page)
        self.page_map[table_name] = (page, idx)
        return idx

    def on_tree_click(self, item, col):
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
                self.create_table_page(new_name, ["id (int)"], [[1]])
                page_index = self.page_map[new_name][1]
                self.stacked_center.setCurrentIndex(page_index)
                print(f"Created new table in {parent.text(0)}: {new_name}")
        elif role == "table":
            table_name = item.text(0)
            if table_name not in self.page_map:
                columns = [["Id", "Int", "Null"],
                           ["Field_1", "String", "NotNull"],
                           ["Field_2", "Money", "Null"]]
                rows = [
                    [1, "Gasparyan", "$200000"],
                    [2, "Hovsepyan", "$300000"],
                    [3, "Sahakyan", "$250000"],
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
