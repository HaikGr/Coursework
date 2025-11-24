# dashboard.py
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea,
    QFrame, QTreeWidget, QTreeWidgetItem,
    QStackedWidget, QTableWidget, QTableWidgetItem, QLineEdit, QGraphicsDropShadowEffect,
    QHeaderView, QSizePolicy, QMessageBox, QDialog, QDialogButtonBox, QComboBox
)
from PyQt6.QtCore import (
    Qt, QPoint, QEvent, QPropertyAnimation, QRect, pyqtSignal, QTimer
)
from PyQt6.QtGui import QColor, QPainter, QPixmap, QIcon, QPen, QCursor
import sys

# ---------------------------
# Diagram canvas (draws connections)
# ---------------------------
class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = []   # list of (TableCardA, fieldA, TableCardB, fieldB)
        self.cards = []
        self.selected_field = None
        self.popup = None

    def add_card(self, card):
        card.canvas = self
        self.cards.append(card)
        card.moved.connect(self.update)  # repaint when card moves

        # register all field click events
        for fr in card.field_rows:
            fr.clicked.connect(self.on_field_clicked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#69a7ff"))
        pen.setWidth(3)
        painter.setPen(pen)

        for A, fieldA, B, fieldB in self.connections:
            # fieldA and fieldB are FieldRow instances
            # compute coordinates in canvas space
            ax = A.x() + A.width()
            ay = A.y() + fieldA.y() + fieldA.height() // 2

            bx = B.x()
            by = B.y() + fieldB.y() + fieldB.height() // 2

            # draw a simple bezier-ish polyline (or straight)
            painter.drawLine(int(ax), int(ay), int(bx), int(by))

    def on_field_clicked(self, field_row):
        # field_row is FieldRow
        if self.selected_field is None:
            self.selected_field = field_row
            # show popup for first selection
            self.show_condition_popup(field_row)
        else:
            # create connection between selected_field and clicked field_row
            A = self.selected_field.table_card
            B = field_row.table_card
            # Avoid self-connection same field
            if A is field_row.table_card and self.selected_field is field_row:
                self.selected_field = None
                self.hide_condition_popup()
                return

            self.connections.append((self.selected_field.table_card, self.selected_field, B, field_row))
            self.selected_field = None
            self.hide_condition_popup()
            self.update()

    def show_condition_popup(self, field_row):
        # ensure a single popup anchored near the field_row
        if self.popup:
            self.popup.hide()
            self.popup.deleteLater()
            self.popup = None

        self.popup = ConditionPopup(self, field_row.table_card.table_name, field_row.field_name)
        # position popup to the right of the field row (in canvas coords)
        pos_in_canvas = field_row.mapTo(self, QPoint(field_row.width(), 0))
        x = field_row.table_card.x() + field_row.width() + 10
        y = field_row.table_card.y() + field_row.y() - 5
        self.popup.move(int(x), int(y))
        self.popup.show()

        # Connect popup hide timer control
        # if mouse leaves both field and popup, hide after 300ms
        def maybe_hide():
            # check if cursor is over popup or field
            global_pos = QCursor.pos()
            rect_popup = self.popup.rect()
            top_left = self.popup.mapToGlobal(rect_popup.topLeft())
            bottom_right = self.popup.mapToGlobal(rect_popup.bottomRight())
            popup_global_rect = QRect(top_left, bottom_right)

            rect_field = field_row.rect()
            field_tl = field_row.mapToGlobal(rect_field.topLeft())
            field_br = field_row.mapToGlobal(rect_field.bottomRight())
            field_global_rect = QRect(field_tl, field_br)

            if not (popup_global_rect.contains(global_pos) or field_global_rect.contains(global_pos)):
                if self.popup:
                    self.popup.hide()

        # install event listeners to keep popup visible while hovering
        # use singleShot timer to check after short delay to avoid flicker
        field_row.entered_callback = lambda: None
        field_row.left_callback = lambda: QTimer.singleShot(160, maybe_hide)
        self.popup.entered_callback = lambda: None
        self.popup.left_callback = lambda: QTimer.singleShot(160, maybe_hide)

    def hide_condition_popup(self):
        if self.popup:
            self.popup.hide()
            self.popup.deleteLater()
            self.popup = None

# Condition Class
class ConditionPopup(QWidget):
    """Floating condition input like your second screenshot"""
    def __init__(self, parent, table_name, field_name):
        super().__init__(parent)
        self.setFixedSize(260, 72)
        self.setStyleSheet("""
            QWidget {
                background-color: #101827;
                border: 1px solid #2E3A4A;
                border-radius: 10px;
            }
            QLineEdit {
                background-color: #0D121A;
                border: 1px solid #3B4757;
                border-radius: 6px;
                padding: 6px;
                color: white;
                font-size: 14px;
            }
            QLabel {
                color: #7C8A99;
                font-size: 12px;
                padding-left: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        title = QLabel(f"{table_name}.{field_name}")
        title.setStyleSheet("color: #9FB6D7; font-size: 12px;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("e.g. >100   (Press Enter to add)")

        layout.addWidget(title)
        layout.addWidget(self.input)

        # allow hover detection
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, event):
        # keep visible; optional callback if set
        if hasattr(self, "entered_callback"):
            try:
                self.entered_callback()
            except Exception:
                pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, "left_callback"):
            try:
                self.left_callback()
            except Exception:
                pass
        return super().leaveEvent(event)

# ---------------------------
# FieldRow & TableCard
# ---------------------------
class FieldRow(QFrame):
    clicked = pyqtSignal(object)  # emits itself
    def __init__(self, table_card, field_name):
        super().__init__(table_card)
        self.table_card = table_card
        self.field_name = field_name
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QFrame { background-color: transparent; border-radius: 6px; }
            QLabel { color: #E0E0E0; padding-left: 8px; font-size: 13px; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.label = QLabel(field_name)
        layout.addWidget(self.label)
        layout.addStretch()

        # enable hover tracking
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        return super().mousePressEvent(event)

    def enterEvent(self, event):
        # show popup via canvas if available
        if hasattr(self.table_card, "canvas") and self.table_card.canvas:
            self.table_card.canvas.show_condition_popup(self)
        # optional callback integration
        if hasattr(self, "entered_callback"):
            try:
                self.entered_callback()
            except Exception:
                pass
        return super().enterEvent(event)

    def leaveEvent(self, event):
        # start a delayed hide check handled by canvas popup logic
        if hasattr(self, "left_callback"):
            try:
                self.left_callback()
            except Exception:
                pass
        return super().leaveEvent(event)

class TableCard(QFrame):
    moved = pyqtSignal()
    def __init__(self, table_name, fields):
        super().__init__()
        self.table_name = table_name
        self.fields = fields
        self.drag_pos = None
        self.condition_popup = None
        self.canvas = None  # set by diagram canvas when added

        self.setFixedSize(240, 240)
        self.setStyleSheet("""
            QFrame {
                background-color: #2E3641;
                border-radius: 10px;
                border: 1px solid #4A4F55;
            }
            QLabel { color: white; font-size: 14px; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)

        self.field_rows = []
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel(self.table_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet("background-color: #2ecc71; border-radius: 5px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(dot)
        layout.addLayout(header)

        # fields
        for f in self.fields:
            row = FieldRow(self, f)
            # row styling container to look like pill
            pill = QFrame()
            pill_layout = QVBoxLayout(pill)
            pill_layout.setContentsMargins(0, 0, 0, 0)
            pill_layout.addWidget(row)
            pill.setStyleSheet("background-color: #3A424F; border-radius: 8px;")
            layout.addWidget(pill)
            # keep reference to the actual row for geometry computations
            self.field_rows.append(row)

        layout.addStretch()

        # right-side small arrow drawn as label
        arrow = QLabel(self)
        arrow_pix = QPixmap(22, 22)
        arrow_pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(arrow_pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#A6B0BD"))
        p.setBrush(QColor("#A6B0BD"))
        # triangle
        p.drawPolygon(
            QPoint(5, 5), QPoint(17, 11), QPoint(5, 17)
        )
        p.end()
        arrow.setPixmap(arrow_pix)
        arrow.move(self.width() - 28, self.height() // 2 - 10)
        arrow.show()

    # dragging behavior (emit moved)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            self.raise_()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            # ensure integer coords
            self.move(int(new_pos.x()), int(new_pos.y()))
            # notify canvas to repaint connections
            self.moved.emit()
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        return super().mouseReleaseEvent(event)

# ---------------------------
# TopBar, SideBar, SQLBuilder, Toolbar, TableDetailsPage remain mostly unchanged
# (I will reuse your original implementations, with minimal edits to integrate)
# ---------------------------

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

        sidebar_layout.addWidget(databases_text)
        sidebar_layout.addWidget(self.db_tree)
        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(new_db_button)
        sidebar_layout.addWidget(logout_button)

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

class InputFieldsWindow(QDialog):
    def __init__(self, types_list=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Input Dialog")
        self.setFixedSize(300,160)
        self.return_data = None
        if types_list is None:
            types_list = ["Int", "Money", "String"]
        self.name_label = QLabel("Field_Name")
        self.input_field = QLineEdit()
        self.type_label = QLabel("Type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(types_list)
        self.null_label = QLabel("IsNull:")
        self.null_combo = QComboBox()
        self.null_combo.addItems(["Null", "Not Null"])
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.input_field)
        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.type_label)
        hlayout1.addWidget(self.type_combo)
        layout.addLayout(hlayout1)
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.null_label)
        hlayout2.addWidget(self.null_combo)
        layout.addLayout(hlayout2)
        layout.addWidget(self.buttons)

    def accept(self):
        field_name = self.input_field.text().strip()
        type_value = self.type_combo.currentText()
        isnull_value = self.null_combo.currentText()
        if not field_name:
            return
        self.return_data = [field_name, type_value, isnull_value]
        super().accept()

    def get_data(self):
        return self.return_data

class TableDetailsPage(QWidget):
    def __init__(self, table_name, columns, rows, stacked):
        super().__init__()
        self.table_name = table_name
        self.columns = columns
        self.rows = rows
        self.stacked = stacked
        self.input_window = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # minimal styling fallback (you had qss file originally)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        toolbar = Toolbar()
        layout.addWidget(toolbar)
        go_back = QPushButton("<- Back")
        go_back.clicked.connect(self.go_back)
        layout.addWidget(go_back)
        header = QLabel(f"Table: {table_name}")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)
        schema_frame = QFrame()
        sf_layout = QVBoxLayout(schema_frame)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.addWidget(QLabel("Schema:"))
        self.scheme = QTableWidget()
        self.scheme.setRowCount(len(columns))
        scheme_columns = ["FieldName", "Type", "IsNull"]
        self.scheme.setColumnCount(len(scheme_columns))
        self.scheme.setHorizontalHeaderLabels(scheme_columns)
        self.scheme.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scheme.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for r_idx, r in enumerate(columns):
            for c_idx, value in enumerate(r):
                self.scheme.setItem(r_idx, c_idx, QTableWidgetItem(str(value)))
        layout.addWidget(self.scheme)
        self.add_fields = QPushButton("Add Field")
        self.add_fields.clicked.connect(self.add_field)
        layout.addWidget(self.add_fields)
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels([x[0] for x in columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for r_idx, r in enumerate(rows):
            for c_idx, value in enumerate(r):
                self.table.setItem(r_idx, c_idx, QTableWidgetItem(str(value)))
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.setFocus()
        layout.addWidget(self.table)
        add_rows = QPushButton("Add Row")
        add_rows.clicked.connect(self.add_rows)
        layout.addWidget(add_rows)

    def add_rows(self):
        new_row = ["Unknown" for i in range(len(self.columns))]
        self.rows.append(new_row)
        new_row_index = len(self.rows) - 1
        self.table.setRowCount(len(self.rows))
        for col, value in enumerate(new_row):
            self.table.setItem(new_row_index, col, QTableWidgetItem(str(value)))

    def add_field(self):
        field_info = InputFieldsWindow()
        result = field_info.exec()
        if result == QDialog.DialogCode.Accepted:
            new_data = field_info.get_data()
            if not new_data:
                return
            field_name, type_value, isnull_value = new_data
            current_columns = self.table.columnCount()
            self.table.insertColumn(current_columns)
            self.table.setHorizontalHeaderItem(current_columns, QTableWidgetItem(field_name))
            current_rows = self.scheme.rowCount()
            self.scheme.insertRow(current_rows)
            for col_index, value in enumerate(new_data):
                self.scheme.setItem(current_rows, col_index, QTableWidgetItem(value))
            self.columns.append(new_data)

    def delete_selected_rows(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            return
        for row in sorted(selected_rows, reverse=True):
            self.table.removeRow(row)
            del self.rows[row]

    def delete_selected_field(self):
        selected_items = self.scheme.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a field to delete.")
            return
        selected_row = selected_items[0].row()
        field_name = self.scheme.item(selected_row, 0).text()
        reply = QMessageBox.question(
            self,
            "Delete Field",
            f"Are you sure you want to delete the field '{field_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        column_index = selected_row
        self.table.removeColumn(column_index)
        self.scheme.removeRow(selected_row)
        del self.columns[selected_row]
        for row_data in self.rows:
            if column_index < len(row_data):
                del row_data[column_index]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = set()
            for item in self.table.selectedItems():
                selected_rows.add(item.row())
            if selected_rows:
                reply = QMessageBox.question(
                    self,
                    "Delete Row(s)",
                    "Do you want to delete the selected row(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for row in sorted(selected_rows, reverse=True):
                        self.table.removeRow(row)
                        del self.rows[row]
                return
            selected_columns = set()
            for item in self.scheme.selectedItems():
                selected_columns.add(item.row())
            if selected_columns:
                reply = QMessageBox.question(
                    self,
                    "Delete Field(s)",
                    "Do you want to delete the selected field(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for col_index in sorted(selected_columns, reverse=True):
                        self.table.removeColumn(col_index)
                        self.scheme.removeRow(col_index)
                        if col_index < len(self.columns):
                            del self.columns[col_index]
                        for row_data in self.rows:
                            if col_index < len(row_data):
                                del row_data[col_index]
        else:
            super().keyPressEvent(event)

    def go_back(self):
        self.stacked.setCurrentIndex(0)

# ---------------------------
# Diagram Page (draggable cards)
# ---------------------------
class DiagramPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = Toolbar()
        layout.addWidget(toolbar)

        # large scrollable canvas area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # We'll use a DiagramCanvas inside the scroll area
        self.table_area = DiagramCanvas()
        self.table_area.setMinimumSize(1400, 900)
        self.table_area.setStyleSheet("background-color: #f5f6f7;")

        container_layout.addWidget(self.table_area)

        # Add example cards
        card1 = TableCard("Users", ["user_id (PK)", "username", "email", "created_at"])
        card1.move(120, 80)
        card1.setParent(self.table_area)
        self.table_area.add_card(card1)

        card2 = TableCard("Orders", ["order_id (PK)", "user_fk", "order_date", "total_amount"])
        card2.move(420, 220)
        card2.setParent(self.table_area)
        self.table_area.add_card(card2)

        card3 = TableCard("Products", ["product_id (PK)", "name", "price", "category"])
        card3.move(760, 120)
        card3.setParent(self.table_area)
        self.table_area.add_card(card3)

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
        at_layout = QVBoxLayout(add_table_page)
        at_layout.addWidget(QLabel("New table created. Click the tree to open its page."))
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
