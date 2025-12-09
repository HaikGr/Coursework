from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton,
    QFrame, QTreeWidget, QTreeWidgetItem, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from items.TableDetailsPage import TableDetailsPage, show_styled_question, show_styled_message
from items.InputTableNameWindow import InputTableNameWindow
from items.InputDatabaseWindow import InputDatabaseWindow


class SideBar(QWidget):
    def __init__(self, stack_widget):
        super().__init__()
        self.stacked_center = stack_widget
        self.page_map = {}
        self.db_counter = 0
        
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.setLayout(sidebar_layout)
        self.setFixedWidth(260)
        self.setStyleSheet("background-color: #FFFFFF;")

        # Header
        databases_text = QFrame()
        databases_text.setFixedHeight(44)
        databases_text.setStyleSheet("""
            QFrame {
                background-color: #fbc840;
                border: none;
            }
        """)
        dt_layout = QHBoxLayout(databases_text)
        dt_layout.setContentsMargins(16, 0, 16, 0)
        lbl_db = QLabel("Databases")
        lbl_db.setStyleSheet("color: #744210; font-size: 16px; font-weight: 600; background: transparent;")
        dt_layout.addWidget(lbl_db)
        dt_layout.addStretch()

        # Tree widget for databases
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.setIndentation(16)
        self.db_tree.setAnimated(True)
        self.db_tree.setRootIsDecorated(False)
        self.db_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #FFFFFF;
                border: none;
                outline: none;
                font-size: 13px;
            }
            QTreeWidget::item {
                height: 38px;
                padding-left: 0px;
                margin: 0px;
                color: #2D3748;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #F0F4F8;
            }
            QTreeWidget::item:selected {
                background-color: #3777f0;
                color: white;
            }
            QTreeWidget::branch {
                background: transparent;
            }
        """)
        self.db_tree.itemClicked.connect(self.on_tree_click)
        self.db_tree.itemDoubleClicked.connect(self.on_tree_double_click)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.db_tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Add Database button
        self.add_db_button = QPushButton("+ Add Database")
        self.add_db_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_db_button.setStyleSheet("""
            QPushButton {
                background-color: #F0F4F8;
                color: #4A5568;
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                padding: 10px;
                margin: 10px;
                border: 1px dashed #C6C6C6;
            }
            QPushButton:hover {
                background-color: #E2ECFF;
                border: 1px dashed #3777f0;
                color: #3777f0;
            }
        """)
        self.add_db_button.clicked.connect(self.add_database)

        # Logout button
        logout_button = QPushButton("LOG OUT")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #E34A4A;
                color: white;
                font-size: 14px;
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
        logout_button.clicked.connect(self.logout)

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree, 1)
        sidebar_layout.addWidget(self.add_db_button)
        sidebar_layout.addWidget(logout_button)

    def add_database(self, name=None):
        """Add a new database to the tree"""
        if not name or not isinstance(name, str):
            # Use dark themed dialog
            dialog = InputDatabaseWindow(
                self, 
                title="New Database",
                default_name=f"Database {self.db_counter + 1}",
                button_text="Create Database"
            )
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                return
            name = dialog.get_data()
            if not name:
                return
        
        # Check for duplicate
        for i in range(self.db_tree.topLevelItemCount()):
            if self.db_tree.topLevelItem(i).text(0) == name:
                show_styled_message(self, "Duplicate Database", f"Database '{name}' already exists!", QMessageBox.Icon.Warning)
                return
        
        self.db_counter += 1
        
        # Create database item
        db_item = QTreeWidgetItem([f"☰  {name}"])
        db_item.setData(0, Qt.ItemDataRole.UserRole, "database")
        db_item.setData(0, Qt.ItemDataRole.UserRole + 1, name)
        db_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        db_item.setForeground(0, Qt.GlobalColor.white)
        db_item.setBackground(0, Qt.GlobalColor.transparent)
        
        self.db_tree.addTopLevelItem(db_item)
        
        # Style the database item with blue background
        self.db_tree.setItemWidget(db_item, 0, self._create_db_widget(name))
        
        # Add "Add Table" child
        add_item = QTreeWidgetItem(["     + Add Table"])
        add_item.setData(0, Qt.ItemDataRole.UserRole, "add_table")
        db_item.addChild(add_item)
        
        db_item.setExpanded(True)

    def _create_db_widget(self, name):
        """Create a styled widget for database item"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #3777f0;
                border-radius: 6px;
                margin: 2px 8px 2px 0px;
            }
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        
        icon = QLabel("☰")
        icon.setStyleSheet("color: white; font-size: 12px; background: transparent;")
        
        label = QLabel(name)
        label.setStyleSheet("color: white; font-size: 13px; font-weight: 600; background: transparent;")
        label.setObjectName("db_name_label")
        
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch()
        
        return widget

    def _create_table_item(self, table_name):
        """Create a styled table item"""
        table_item = QTreeWidgetItem([f"  ⊞  {table_name}"])
        table_item.setData(0, Qt.ItemDataRole.UserRole, "table")
        table_item.setData(0, Qt.ItemDataRole.UserRole + 1, table_name)
        return table_item

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
        
        if role == "database":
            item.setExpanded(not item.isExpanded())
            return
            
        if role == "add_table":
            input_field = InputTableNameWindow()
            result = input_field.exec()

            if result != QDialog.DialogCode.Accepted:
                return

            table_name_received = input_field.get_data()
            if not table_name_received:
                return

            parent = item.parent()
            existing_names = set()
            for i in range(parent.childCount()):
                child = parent.child(i)
                child_role = child.data(0, Qt.ItemDataRole.UserRole)
                if child_role == "table":
                    existing_names.add(child.data(0, Qt.ItemDataRole.UserRole + 1))

            if table_name_received in existing_names:
                show_styled_message(self, "Duplicate Table", f"Table '{table_name_received}' already exists!", QMessageBox.Icon.Warning)
                return

            new_table_item = self._create_table_item(table_name_received)
            parent.insertChild(parent.childCount() - 1, new_table_item)

            self.create_table_page(table_name_received)
            page_index = self.page_map[table_name_received][1]
            self.stacked_center.setCurrentIndex(page_index)
            
        elif role == "table":
            table_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if table_name not in self.page_map:
                self.create_table_page(table_name)
            page_index = self.page_map[table_name][1]
            self.stacked_center.setCurrentIndex(page_index)

    def on_tree_double_click(self, item):
        """Handle double click - rename database"""
        role = item.data(0, Qt.ItemDataRole.UserRole)
        
        if role == "database":
            old_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            # Use dark themed dialog for rename
            dialog = InputDatabaseWindow(
                self,
                title="Rename Database",
                default_name=old_name,
                button_text="Rename"
            )
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                new_name = dialog.get_data()
                if new_name and new_name != old_name:
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, new_name)
                    # Update widget
                    widget = self.db_tree.itemWidget(item, 0)
                    if widget:
                        label = widget.findChild(QLabel, "db_name_label")
                        if label:
                            label.setText(new_name)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            item = self.db_tree.currentItem()
            if not item:
                return

            role = item.data(0, Qt.ItemDataRole.UserRole)

            if role == "table":
                table_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
                confirm = show_styled_question(self, "Delete Table", f"Are you sure you want to delete '{table_name}'?")

                if confirm == QMessageBox.StandardButton.Yes:
                    parent = item.parent()
                    parent.removeChild(item)

                    if table_name in self.page_map:
                        page, idx = self.page_map.pop(table_name)
                        widget = self.stacked_center.widget(idx)
                        self.stacked_center.removeWidget(widget)
                        widget.deleteLater()

                        diagram_page = self.stacked_center.widget(0)
                        diagram_page.remove_table_card(table_name)
                        
            elif role == "database":
                db_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
                confirm = show_styled_question(self, "Delete Database", f"Are you sure you want to delete '{db_name}' and all its tables?")

                if confirm == QMessageBox.StandardButton.Yes:
                    for i in range(item.childCount()):
                        child = item.child(i)
                        if child.data(0, Qt.ItemDataRole.UserRole) == "table":
                            table_name = child.data(0, Qt.ItemDataRole.UserRole + 1)
                            if table_name in self.page_map:
                                page, idx = self.page_map.pop(table_name)
                                widget = self.stacked_center.widget(idx)
                                self.stacked_center.removeWidget(widget)
                                widget.deleteLater()
                                diagram_page = self.stacked_center.widget(0)
                                diagram_page.remove_table_card(table_name)
                    
                    index = self.db_tree.indexOfTopLevelItem(item)
                    self.db_tree.takeTopLevelItem(index)

    def logout(self):
        """Trigger logout by finding the main window and calling its log_out method"""
        main_window = self.window()
        if hasattr(main_window, 'log_out'):
            main_window.log_out()
