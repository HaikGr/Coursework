"""
TableDetailsPage - the schema and the rows of one table, side by side.

What changed is tracked by a TableState (dbmanager.model); this page only shows it and turns
clicks and typing into calls on it.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget
)

from dbmanager.db.values import MAX_TEXT_LENGTH
from dbmanager.model.table_state import NULL_TEXT, TableState, cell_text, is_auto_increment, is_primary_key
from dbmanager.sql import generator as sqlgen
from dbmanager.ui.common.data_grid import SCROLLBAR_STYLE, fit_columns, prepare_grid, set_cell_text
from dbmanager.ui.common.elided_label import ElidedLabel
from dbmanager.ui.common.message_box import confirm, show_styled_message
from dbmanager.ui.common.style import shortcut_text
from dbmanager.ui.common.value_panel import ValuePanel
from dbmanager.ui.dialogs.field_dialog import InputFieldsWindow
from dbmanager.ui.dialogs.not_null_dialog import ask_fill_value
from dbmanager.ui.dialogs.rename_dialog import ask_new_name

ROW_HEIGHT = 42
# The schema's columns: a field's name takes what the type, the NULL box and ⋮ leave, down to NAME_MIN_WIDTH
TYPE_COLUMN_WIDTH = 124
NULL_COLUMN_WIDTH = 50
MORE_BUTTON_WIDTH = 22
NAME_MIN_WIDTH = 56
# Room for a row at its narrowest (margins, a PK badge, the columns, the spacing, the scroll bar): the
# schema panel is never narrower, so its rows never need a sideways scroll bar
SCHEMA_PANEL_MIN_WIDTH = 2 * 12 + 26 + NAME_MIN_WIDTH + TYPE_COLUMN_WIDTH + NULL_COLUMN_WIDTH + MORE_BUTTON_WIDTH + 3 * 6 + 10
VALUE_PANEL_KEYS = ("Shift+Return", "Shift+Enter")

# The cell editor is a QLineEdit inside the table. It must get its colours here: otherwise it takes
# the dashboard's light background together with the table's light text and what you type is invisible.
DATA_TABLE_STYLE = """
    QTableWidget { background-color: #2D3748; alternate-background-color: #323D4D; border: none; color: #E2E8F0; font-size: 12px; }
    QTableWidget::item { padding: 0px 12px; border-bottom: 1px solid #3D4852; }
    QTableWidget::item:selected { background-color: #3777f0; color: #FFFFFF; }
    QTableWidget QLineEdit {
        background-color: #1A202C;
        color: #F7FAFC;
        border: 2px solid #3777f0;
        border-radius: 4px;
        padding: 0px 6px;
        font-size: 12px;
        selection-background-color: #3777f0;
        selection-color: #FFFFFF;
    }
    QHeaderView::section { background-color: #252D3A; color: #718096; padding: 10px 12px; border: none;
                           border-right: 1px solid #2D3748; font-weight: 600; font-size: 11px; }
""" + SCROLLBAR_STYLE

VALUE_BUTTON_STYLE = """
    QPushButton { color: #FFFFFF; background: transparent; border: 1px solid rgba(255, 255, 255, 0.7);
                  border-radius: 4px; padding: 0px 8px; font-size: 11px; font-weight: 600; }
    QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
    QPushButton:checked { background: #FFFFFF; color: #276749; border-color: #FFFFFF; }
"""

SCHEMA_MENU_STYLE = """
    QMenu { background-color: #1f2937; border: 1px solid #374151; border-radius: 6px; padding: 4px; }
    QMenu::item { padding: 8px 16px; color: #f3f4f6; border-radius: 4px; }
    QMenu::item:selected { background-color: #374151; }
    QMenu::separator { height: 1px; background: #374151; margin: 4px 6px; }
"""

DROP_BUTTON_STYLE = """
    QPushButton { background-color: transparent; color: #fca5a5; border: 1px solid #7f1d1d; border-radius: 5px;
                  font-size: 11px; font-weight: 600; padding: 0 10px; }
    QPushButton:hover { background-color: #7f1d1d; color: #fee2e2; }
"""
KEEP_BUTTON_STYLE = """
    QPushButton { background-color: #7f1d1d; color: #fee2e2; border: none; border-radius: 5px;
                  font-size: 11px; font-weight: 600; padding: 0 10px; }
    QPushButton:hover { background-color: #991b1b; }
"""

BOTTOM_BUTTON_STYLE = """
    QPushButton { background-color: #252D3A; color: #A0AEC0; border: none; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; font-size: 12px; }
    QPushButton:hover { background-color: #2D3748; color: #E2E8F0; }
    QPushButton:disabled { color: #4A5568; }
"""


class SchemaRow(QFrame):
    """A field's row in the schema panel; a click on it shows the field in the rows"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()  # so the release comes here too
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()


class TableDetailsPage(QWidget):
    # The value panel is a way of working, not a property of one table: it stays open (or closed) from table
    # to table for the rest of the session
    value_panel_open = False

    table_data_ready = pyqtSignal(str, list)    # columns added: refresh the diagram card
    field_deleted = pyqtSignal(str, list)       # table name, remaining columns
    field_renamed = pyqtSignal(str, str, str, list)  # table name, old name, new name, columns
    changes_made = pyqtSignal()                 # something here now differs from the database
    discard_requested = pyqtSignal(str)         # table name: throw this table's unsaved changes away
    drop_requested = pyqtSignal(str)            # table name: drop it (or keep it after all)

    def __init__(self, table_name, stacked, columns=None, live=False, db_type="POSTGRESQL", view=False,
                 structure_locked=False, constraints=None, column_details=None):
        super().__init__()
        self.state = TableState(table_name, db_type, live=live, view=view, constraints=constraints)
        # A database shared with this user: rows may change (as far as the share allows), its structure not
        self.structure_locked = structure_locked
        # Set by the sidebar: column (its name in the database) -> ["orders.item_code", ...], the keys of other
        # tables that point at it, which dropping it takes along
        self.describe_references = lambda column: []
        # The columns as the database has them, to come back to when the changes are discarded
        self.schema_columns = [list(column) for column in columns or []]
        self.stacked = stacked
        self.schema_rows = []
        self.cell_notice = ""
        self._panel_cell = None      # (row, column) the value panel shows
        self._panel_problem = None   # why the text typed there was not taken

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("QWidget { background-color: #f5f6f7; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background-color: #f5f6f7; }")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        # The schema needs little room; a table with many fields needs all it can get for its rows
        content_layout.addWidget(self._build_schema_panel(), stretch=1)
        content_layout.addWidget(self._build_data_panel(), stretch=2)
        main_layout.addWidget(content_widget)

        for column in columns or []:
            self._append_column(column, origin=column[0], details=(column_details or {}).get(column[0]))

        if not self.state.editable:
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            for button in (self.add_field_btn, self.add_row_btn):
                button.setEnabled(False)
                button.setToolTip("Views are read-only here")
        elif structure_locked:
            self.add_field_btn.setEnabled(False)
            self.add_field_btn.setToolTip("Only the owner changes the structure of a shared database")

    @property
    def table_name(self):
        return self.state.name

    # ---------------- Schema panel ----------------
    @staticmethod
    def _create_panel_shadow(widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        widget.setGraphicsEffect(shadow)

    def _build_schema_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #2D3748; border-radius: 10px; }")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.setMinimumWidth(SCHEMA_PANEL_MIN_WIDTH)
        self._create_panel_shadow(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #2D3748; border-top-left-radius: 10px; border-top-right-radius: 10px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("""
            QPushButton { background-color: #4A5568; color: #E2E8F0; border: none; border-radius: 5px; font-size: 12px; padding: 0 10px; }
            QPushButton:hover { background-color: #5A6A7D; }
        """)

        table_icon = QLabel("⊡" if self.state.view else "⊞")
        table_icon.setStyleSheet("QLabel { font-size: 14px; color: #A0AEC0; background: transparent; }")
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("QLabel { color: #FFFFFF; font-size: 14px; font-weight: 600; "
                                  "background: transparent; }")

        header_layout.addWidget(back_btn)
        header_layout.addSpacing(10)
        header_layout.addWidget(table_icon)
        header_layout.addSpacing(4)
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        if self.state.view:
            view_badge = QLabel("view · read-only")
            view_badge.setStyleSheet("QLabel { color: #A0AEC0; font-size: 11px; background: transparent; }")
            header_layout.addWidget(view_badge)
        self.drop_btn = QPushButton()
        self.drop_btn.setFixedHeight(28)
        self.drop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop_btn.clicked.connect(lambda: self.drop_requested.emit(self.table_name))
        self.drop_btn.setVisible(not self.structure_locked)
        header_layout.addWidget(self.drop_btn)
        self.show_pending_drop(False)
        layout.addWidget(header)

        # Schema header
        schema_header = QFrame()
        schema_header.setFixedHeight(32)
        schema_header.setStyleSheet("QFrame { background-color: #fbc840; }")
        schema_header_layout = QHBoxLayout(schema_header)
        schema_header_layout.setContentsMargins(12, 0, 12, 0)
        schema_icon = QLabel("⊞")
        schema_icon.setStyleSheet("QLabel { font-size: 12px; color: #744210; background: transparent; }")
        schema_title = QLabel("Schema")
        schema_title.setStyleSheet("QLabel { color: #744210; font-size: 12px; font-weight: 600; "
                                   "background: transparent; }")
        schema_header_layout.addWidget(schema_icon)
        schema_header_layout.addSpacing(4)
        schema_header_layout.addWidget(schema_title)
        schema_header_layout.addStretch()
        layout.addWidget(schema_header)

        # Column headers
        col_header = QFrame()
        col_header.setFixedHeight(36)
        col_header.setStyleSheet("QFrame { background-color: #252D3A; }")
        col_header_layout = QHBoxLayout(col_header)
        col_header_layout.setContentsMargins(12, 0, 12, 0)
        col_header_layout.setSpacing(6)  # as in the rows below, so the headings stand over their columns
        header_style = "QLabel { color: #718096; font-size: 11px; font-weight: 600; background: transparent; }"
        col_label = QLabel("Column")
        col_label.setStyleSheet(header_style)
        type_label = QLabel("Type")
        type_label.setStyleSheet(header_style)
        type_label.setFixedWidth(TYPE_COLUMN_WIDTH)
        null_label = QLabel("Null")
        null_label.setStyleSheet(header_style)
        null_label.setFixedWidth(NULL_COLUMN_WIDTH)
        null_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        col_header_layout.addWidget(col_label, 1)
        col_header_layout.addWidget(type_label)
        col_header_layout.addWidget(null_label)
        if self.state.editable and not self.structure_locked:
            col_header_layout.addSpacing(MORE_BUTTON_WIDTH)  # over the rows' ⋮
        layout.addWidget(col_header)

        # Schema rows
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # names are cut instead
        scroll_area.setStyleSheet("""
            QScrollArea { background-color: #2D3748; border: none; }
            QWidget { background-color: #2D3748; }
            QScrollBar:vertical { background: #2D3748; width: 6px; }
            QScrollBar::handle:vertical { background: #4A5568; border-radius: 3px; }
        """)
        self.schema_container = QWidget()
        self.schema_container.setStyleSheet("QWidget { background-color: #2D3748; }")
        self.schema_layout = QVBoxLayout(self.schema_container)
        self.schema_layout.setContentsMargins(0, 0, 0, 0)
        self.schema_layout.setSpacing(0)
        self.schema_layout.addStretch()
        scroll_area.setWidget(self.schema_container)
        layout.addWidget(scroll_area)

        self.add_field_btn = QPushButton("+ Add Field")
        self.add_field_btn.setFixedHeight(38)
        self.add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_field_btn.clicked.connect(self.add_field)
        self.add_field_btn.setStyleSheet(BOTTOM_BUTTON_STYLE)
        layout.addWidget(self.add_field_btn)
        return panel

    def _create_schema_row(self, field_name, type_value, is_nullable, is_pk=False, is_fk=False):
        row_frame = SchemaRow()
        row_frame.setObjectName("schemaRow")
        row_frame.setFixedHeight(42)
        row_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        # Named: a QLabel is a QFrame too, and a plain QFrame rule drew the row's bottom line under each name
        row_frame.setStyleSheet("""
            QFrame#schemaRow { background-color: #2D3748; border-bottom: 1px solid #3D4852; }
            QFrame#schemaRow:hover { background-color: #3D4A5C; }
        """)
        row_frame.clicked.connect(lambda f=row_frame: self._show_field_of_row(f))
        structure_editable = self.state.editable and not self.structure_locked
        hint = "Click to show it in the rows"
        if structure_editable:
            hint += " · ⋮ or right-click: rename, require a value or allow NULL, delete"
            row_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            row_frame.customContextMenuRequested.connect(
                lambda pos, f=row_frame: self._show_schema_context_menu(f, f.mapToGlobal(pos)))
        row_frame.setToolTip(f"{field_name} ({type_value})\n{hint}")

        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(6)

        name_container = QWidget()
        name_container.setStyleSheet("QWidget { background: transparent; }")
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)
        if is_pk or is_fk:
            # A text badge, as on the diagram: an emoji key shows as an empty box without an emoji font
            icon = QLabel("PK" if is_pk else "FK")
            icon.setFixedSize(22, 14)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = "#f6c344" if is_pk else "#60a5fa"
            icon.setStyleSheet(f"QLabel {{ color: {color}; border: 1px solid {color}; border-radius: 3px; "
                               "font-size: 8px; font-weight: 700; background: transparent; }")
            name_layout.addWidget(icon)
        # A long name is cut with …, whole in its tooltip
        name_label = ElidedLabel(field_name)
        name_label.setMinimumWidth(NAME_MIN_WIDTH)
        name_label.setObjectName("field_name_label")
        name_label.setStyleSheet("QLabel { color: #E2E8F0; font-size: 12px; background: transparent; }")
        name_layout.addWidget(name_label)

        type_badge = QLabel()
        type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_badge.setFixedHeight(22)
        type_badge.setMinimumWidth(70)
        type_badge.setStyleSheet("QLabel { background-color: #4A5568; color: #E2E8F0; border-radius: 4px; font-size: 10px; padding: 0 8px; }")
        type_badge.ensurePolished()  # its own font size counts
        shown_type = type_badge.fontMetrics().elidedText(type_value, Qt.TextElideMode.ElideRight,
                                                        TYPE_COLUMN_WIDTH - 2 * 8 - 2)
        type_badge.setText(shown_type)
        if shown_type != type_value:
            type_badge.setToolTip(type_value)
        type_container = QWidget()
        type_container.setStyleSheet("QWidget { background: transparent; }")
        type_container.setFixedWidth(TYPE_COLUMN_WIDTH)
        type_layout = QHBoxLayout(type_container)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.addWidget(type_badge)
        type_layout.addStretch()

        null_container = QWidget()
        null_container.setStyleSheet("QWidget { background: transparent; }")
        null_container.setFixedWidth(NULL_COLUMN_WIDTH)
        null_layout = QHBoxLayout(null_container)
        null_layout.setContentsMargins(0, 0, 0, 0)
        null_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if is_nullable:
            null_dot = QLabel("●")
            null_dot.setStyleSheet("QLabel { color: #48BB78; font-size: 12px; background: transparent; }")
            null_layout.addWidget(null_dot)
        checkbox_frame = QFrame()
        checkbox_frame.setFixedSize(14, 14)
        if is_nullable:
            checkbox_frame.setStyleSheet("QFrame { background-color: rgba(72, 187, 120, 0.3); border: 2px solid #48BB78; border-radius: 3px; }")
        else:
            checkbox_frame.setStyleSheet("QFrame { background-color: transparent; border: 2px solid #4A5568; border-radius: 3px; }")
        null_layout.addWidget(checkbox_frame)

        row_layout.addWidget(name_container, 1)
        row_layout.addWidget(type_container)
        row_layout.addWidget(null_container)
        if structure_editable:
            more = QToolButton()
            more.setText("⋮")
            more.setFixedWidth(MORE_BUTTON_WIDTH)
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setToolTip("Rename, require a value or allow NULL, delete")
            more.setStyleSheet("""
                QToolButton { color: #A0AEC0; background: transparent; border: none; border-radius: 4px;
                              font-size: 15px; font-weight: bold; padding: 0 4px; }
                QToolButton:hover { color: #FFFFFF; background: #4A5568; }
            """)
            more.clicked.connect(lambda _=False, f=row_frame, b=more: self._show_schema_context_menu(
                f, b.mapToGlobal(b.rect().bottomLeft())))
            row_layout.addWidget(more)
        return row_frame

    def field_menu(self, col_index):
        """What can be done with a field's definition: rename it, require a value or allow NULL, delete it"""
        column = self.state.columns[col_index]
        menu = QMenu(self)
        menu.setStyleSheet(SCHEMA_MENU_STYLE)
        menu.addAction("Rename field…").triggered.connect(lambda: self._rename_field(col_index))
        if self.state.column_meta[col_index]["origin"] is None and not is_auto_increment(column):
            menu.addAction("Default value…").triggered.connect(lambda: self._set_default(col_index))
        if not is_primary_key(column) and not is_auto_increment(column):
            if column[2] == "Null":
                menu.addAction("Require a value (NOT NULL)…").triggered.connect(
                    lambda: self._require_value(col_index))
            else:
                menu.addAction("Allow empty values (NULL)").triggered.connect(
                    lambda: self._allow_null(col_index))
        menu.addSeparator()
        menu.addAction("Delete field…").triggered.connect(lambda: self._delete_field(col_index))
        return menu

    def _show_schema_context_menu(self, row_frame, global_pos):
        if row_frame in self.schema_rows:
            self.field_menu(self.schema_rows.index(row_frame)).exec(global_pos)

    def _show_field_of_row(self, row_frame):
        if row_frame in self.schema_rows:
            self.show_field_in_rows(self.schema_rows.index(row_frame))

    def show_field_in_rows(self, col_index):
        """Scroll the rows to a field. On the row you are on its cell becomes the current one, so the value
        panel shows it: with many fields, the quickest way through one row."""
        if col_index >= self.table.columnCount():
            return
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount():
            self.table.setCurrentCell(row, col_index)
        else:
            self.table.horizontalScrollBar().setValue(self.table.horizontalHeader().sectionPosition(col_index))

    def _refresh_schema_row(self, col_index):
        """Draw a field's row again (its NULL setting changed)"""
        field_name, type_value, null_flag, key_flag = self.state.columns[col_index][:4]
        old = self.schema_rows[col_index]
        fresh = self._create_schema_row(field_name, type_value, null_flag == "Null", key_flag == "PK",
                                        key_flag == "FK")
        self.schema_layout.replaceWidget(old, fresh)
        self.schema_rows[col_index] = fresh
        old.deleteLater()

    def _require_value(self, col_index):
        column = self.state.columns[col_index]
        fill = None
        if self.state.column_meta[col_index]["origin"] is not None:
            # The database checks the rows it already has: those without a value need one first
            missing = len(self.state.rows_without_value(col_index))
            fill = ask_fill_value(self, self.table_name, column[0], column[1], missing,
                                  self.state.rows_truncated or not self.state.rows_loaded)
            if fill is None:
                return
        self.state.set_nullable(col_index, False, fill=fill)
        self._refresh_schema_row(col_index)
        self._changed()

    def _set_default(self, col_index):
        """The default of a field added here (not saved yet): what rows get when no value is given"""
        column = self.state.columns[col_index]
        current = column[7] if len(column) > 7 and column[7] is not None else ""
        value = ask_new_name(self, "Default Value", f"Default value for {column[0]} ({column[1]}) - "
                                                   "empty for none:", current)
        if value is None:
            return
        problem = sqlgen.value_problem(value, column[1])
        if problem:
            show_styled_message(self, "Default Value", f"{column[0]} {problem}.", QMessageBox.Icon.Warning)
            return
        for row, shown in self.state.set_default(col_index, value):
            self._show_cell(row, col_index, shown)
        self._changed()
        self._sync_value_panel()

    def _allow_null(self, col_index):
        self.state.set_nullable(col_index, True)
        self._refresh_schema_row(col_index)
        self._changed()

    def show_pending_drop(self, pending):
        """The table is marked to be dropped at the next Run (or not): the button takes it back"""
        kind = "view" if self.state.view else "table"
        self.drop_btn.setText(f"Keep {kind}" if pending else f"Drop {kind}")
        self.drop_btn.setStyleSheet(KEEP_BUTTON_STYLE if pending else DROP_BUTTON_STYLE)
        self.drop_btn.setToolTip(f"Marked to be dropped when you click Run Query - click to keep the {kind}"
                                 if pending else f"Drop this {kind} from the database (at the next Run Query)")

    def _rename_field(self, col_index):
        if col_index >= len(self.state.columns):
            return
        old_name = self.state.columns[col_index][0]
        new_name = ask_new_name(self, "Rename Field", "Enter new field name:", old_name)
        if not new_name or new_name == old_name:
            return
        if self.state.has_column(new_name, ignore_index=col_index):
            show_styled_message(self, "Rename Field", f"'{self.table_name}' already has a field named '{new_name}'.",
                                QMessageBox.Icon.Warning)
            return

        self.state.rename_column(col_index, new_name)
        self._refresh_schema_row(col_index)
        self.table.setHorizontalHeaderItem(col_index, self._header_item(self.state.columns[col_index]))
        self.field_renamed.emit(self.table_name, old_name, new_name, self.state.columns)
        self._changed()
        self._sync_value_panel()

    def delete_field(self, col_index):
        """Delete a field, after asking (from its menu here, or from the diagram)"""
        if not self.state.editable or self.structure_locked:
            show_styled_message(self, "Delete Field", "The fields of a view, or of a database shared with you, "
                                                      "cannot be changed here.", QMessageBox.Icon.Warning)
            return
        self._delete_field(col_index)

    def _delete_field(self, col_index):
        if col_index >= len(self.state.columns):
            return
        field_name = self.state.columns[col_index][0]
        origin = self.state.column_meta[col_index]["origin"]
        text = f"Delete the field '{field_name}'"
        if origin is None:
            text += "? It was never saved."
        else:
            text += " and its values from every row? It is dropped when you click Run Query."
            references = self.describe_references(origin)
            if references:
                text += ("\n\nThese fields point at it - their foreign keys are dropped too (the fields and their "
                         "values stay):\n  " + "\n  ".join(references))
        if not confirm(self, "Delete Field", text):
            return

        self.state.delete_column(col_index)
        self.table.removeColumn(col_index)
        self.schema_rows.pop(col_index).deleteLater()
        self.field_deleted.emit(self.table_name, self.state.columns)
        self._changed()
        self._sync_value_panel()

    def _existing_rows(self):
        """How many rows the table has in the database: 0 for a new table, None when not all were read"""
        if not self.state.live:
            return 0
        if self.state.rows_truncated or not self.state.rows_loaded:
            return None
        return sum(1 for origin in self.state.row_origin if origin is not None)

    def add_field(self):
        dialog = InputFieldsWindow(existing_names=self.state.column_names(), parent=self,
                                   existing_rows=self._existing_rows())
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.get_data():
            return
        self._append_column(dialog.get_data())
        self.table_data_ready.emit(self.table_name, self.state.columns)
        self._changed()

    def _append_column(self, column, origin=None, details=None):
        """Add one column (name, type, Null/Not Null, PK/FK/-, fk_table, fk_field[, AUTO, default]) to both panels.
        origin is the column's name in the database, or None for a column added here; details, what the
        schema says of it (see db.schema)."""
        field_name, type_value, null_flag, key_flag = column[:4]
        col_index = len(self.state.columns)
        defaults = self.state.add_column(column, origin, details)

        self.table.insertColumn(col_index)
        self.table.setHorizontalHeaderItem(col_index, self._header_item(column))
        schema_row = self._create_schema_row(field_name, type_value, null_flag == "Null",
                                             key_flag == "PK", key_flag == "FK")
        self.schema_rows.append(schema_row)
        self.schema_layout.insertWidget(self.schema_layout.count() - 1, schema_row)
        for row_index, value in enumerate(defaults):
            self._show_cell(row_index, col_index, value)
        fit_columns(self.table, [col_index])

    @staticmethod
    def _header_item(column):
        """A column's heading in the rows; a long name is cut there, so its tooltip has it whole, with its type"""
        item = QTableWidgetItem(column[0])
        item.setToolTip(f"{column[0]} ({column[1]})")
        return item

    # ---------------- Data panel ----------------
    def _build_data_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #2D3748; border-radius: 10px; }")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._create_panel_shadow(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #2D3748; border-top-left-radius: 10px; border-top-right-radius: 10px; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        table_icon = QLabel("⊞")
        table_icon.setStyleSheet("QLabel { font-size: 14px; color: #A0AEC0; background: transparent; }")
        table_label = QLabel(self.table_name)
        table_label.setStyleSheet("QLabel { color: #FFFFFF; font-size: 14px; font-weight: 600; "
                                  "background: transparent; }")
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet("QLabel { background-color: #4A5568; color: #E2E8F0; padding: 4px 10px; "
                                           "border-radius: 10px; font-size: 11px; }")
        header_layout.addWidget(table_icon)
        header_layout.addSpacing(4)
        header_layout.addWidget(table_label)
        header_layout.addStretch()

        self.pending_label = QLabel("● unsaved - Run to save")
        self.pending_label.setStyleSheet("QLabel { color: #fbbf24; font-size: 11px; font-weight: 600; "
                                         "background: transparent; }")
        self.pending_label.setToolTip("These changes are in the SQL panel. Click Run Query to save them to the database.")
        self.pending_label.hide()
        header_layout.addWidget(self.pending_label)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setFixedHeight(22)
        self.discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_btn.setToolTip("Throw away this table's changes that have not been run yet")
        self.discard_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #991b1b; color: #fee2e2; }
        """)
        self.discard_btn.clicked.connect(lambda: self.discard_requested.emit(self.table_name))
        self.discard_btn.hide()
        header_layout.addWidget(self.discard_btn)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.row_count_label)
        layout.addWidget(header)

        # Data header
        data_header = QFrame()
        data_header.setFixedHeight(32)
        data_header.setStyleSheet("QFrame { background-color: #48BB78; }")
        data_header_layout = QHBoxLayout(data_header)
        data_header_layout.setContentsMargins(12, 0, 12, 0)
        data_icon = QLabel("≡")
        data_icon.setStyleSheet("QLabel { font-size: 12px; color: #FFFFFF; background: transparent; }")
        data_title = QLabel("Data Records")
        data_title.setStyleSheet("QLabel { color: #FFFFFF; font-size: 12px; font-weight: 600; "
                                 "background: transparent; }")
        data_header_layout.addWidget(data_icon)
        data_header_layout.addSpacing(4)
        data_header_layout.addWidget(data_title)
        data_header_layout.addStretch()
        self.value_btn = QPushButton("⊟  Value")
        self.value_btn.setCheckable(True)
        self.value_btn.setFixedHeight(22)
        self.value_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.value_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.value_btn.setToolTip("Show the whole value of the selected cell under the rows "
                                  f"({shortcut_text(VALUE_PANEL_KEYS[0])})")
        self.value_btn.setStyleSheet(VALUE_BUTTON_STYLE)
        self.value_btn.toggled.connect(self._on_value_toggled)
        data_header_layout.addWidget(self.value_btn)
        layout.addWidget(data_header)

        # What the database would refuse in the changes, and a value that was not taken
        self.problems_label = QLabel()
        self.problems_label.setWordWrap(True)
        self.problems_label.setStyleSheet("""
            QLabel { color: #fde68a; background-color: #422006; border-left: 3px solid #f59e0b;
                     font-size: 11px; padding: 8px 12px; }
        """)
        self.problems_label.hide()
        layout.addWidget(self.problems_label)

        # Data table: columns sized to what they hold, scrolling sideways when there are many (see data_grid)
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        prepare_grid(self.table)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.currentCellChanged.connect(lambda *_: self._sync_value_panel())
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setStyleSheet(DATA_TABLE_STYLE)
        for keys in VALUE_PANEL_KEYS:
            shortcut = QShortcut(QKeySequence(keys), self.table)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(self.open_value_panel)

        # The whole value of the current cell, under the rows: their columns keep the width of the grid
        self.value_panel = ValuePanel()
        self.value_panel.hide()
        self.value_panel.edited.connect(self._on_panel_edited)
        self.value_panel.editing_finished.connect(self._on_panel_left)
        self.value_panel.leave_requested.connect(self.table.setFocus)
        self.value_panel.closed.connect(lambda: self.value_btn.setChecked(False))

        self.rows_split = QSplitter(Qt.Orientation.Vertical)
        self.rows_split.setStyleSheet("QSplitter::handle { background-color: #3D4852; }")
        self.rows_split.setHandleWidth(3)
        self.rows_split.setChildrenCollapsible(False)
        self.rows_split.addWidget(self.table)
        self.rows_split.addWidget(self.value_panel)
        self.rows_split.setStretchFactor(0, 1)
        self.rows_split.setStretchFactor(1, 0)
        layout.addWidget(self.rows_split)

        self.add_row_btn = QPushButton("+ Add Row")
        self.add_row_btn.setFixedHeight(38)
        self.add_row_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_row_btn.clicked.connect(self.add_rows)
        self.add_row_btn.setStyleSheet(BOTTOM_BUTTON_STYLE)
        layout.addWidget(self.add_row_btn)
        return panel

    def _column_type(self, col_index):
        return self.state.columns[col_index][1] if col_index < len(self.state.columns) else ""

    def _is_id_column(self, col_index):
        if col_index >= len(self.state.columns):
            return False
        column = self.state.columns[col_index]
        return is_primary_key(column) or column[0].lower() == "id"

    def _on_cell_changed(self, row, col):
        item = self.table.item(row, col)
        if item is None or row >= len(self.state.rows) or col >= len(self.state.columns):
            return
        self.cell_notice = ""
        problem = self._take_value(row, col, item.text())
        if problem:
            self.cell_notice = self._not_taken(col, problem)
            self._show_problems()
        self._sync_value_panel()

    def _take_value(self, row, col, text):
        """A value typed for a cell, in it or in the value panel. Taken when its column can hold it; otherwise
        the cell keeps its value and this says why - the database would refuse the whole run for it."""
        if sqlgen.is_money_type(self._column_type(col)) and text.strip().startswith("$"):
            text = text.strip()[1:]  # the '$' is only how money is shown
        problem = sqlgen.value_problem(text, self._column_type(col))
        if problem:
            self._show_cell(row, col, self.state.rows[row][col])
            return problem
        self.state.set_cell(row, col, text)
        self._show_cell(row, col, text)
        self._changed()
        return None

    def _not_taken(self, col, problem):
        return f"{self.state.columns[col][0]} {problem} - the value was not taken."

    def _value_cut(self, row, col):
        """The database holds more of this value than was read (db.values.MAX_TEXT_LENGTH): saved back, the
        rest would be lost, so it is not edited here"""
        origin = self.state.row_origin[row] if row < len(self.state.row_origin) else None
        name = self.state.column_meta[col]["origin"] if col < len(self.state.column_meta) else None
        value = origin.get(name) if origin and name is not None else None
        return isinstance(value, str) and len(value) >= MAX_TEXT_LENGTH

    def _show_cell(self, row, col, value):
        """Show one value in the data table, styled by its column."""
        self.table.blockSignals(True)
        try:
            text = cell_text(value)
            column_type = self._column_type(col)
            if sqlgen.is_money_type(column_type) and value is not None and _looks_numeric(text):
                text = f"${text}"

            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            set_cell_text(item, text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # A one-line editor would join the lines of a value: those are edited in the value panel
            in_place = self.state.editable and "\n" not in text and "\r" not in text and not self._value_cut(row, col)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable if in_place
                          else item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if value is None or (isinstance(value, str) and value.strip().upper() == NULL_TEXT):
                item.setForeground(QColor("#718096"))
                item.setFont(self._cell_font(italic=True))
            elif self._is_id_column(col):
                item.setForeground(QColor("#63B3ED"))
                item.setFont(self._cell_font(bold=True))
            elif sqlgen.is_exact_decimal_type(column_type):
                item.setForeground(QColor("#48BB78"))
                item.setFont(self._cell_font(bold=True))
            else:
                item.setForeground(QColor("#E2E8F0"))
        finally:
            self.table.blockSignals(False)

    def _cell_font(self, bold=False, italic=False):
        """The table's own font - the system's, on every platform - only bold or italic"""
        font = QFont(self.table.font())
        font.setBold(bold)
        font.setItalic(italic)
        return font

    def add_rows(self):
        if not self.state.editable:
            return
        if not self.state.columns:
            show_styled_message(self, "No Fields", "Please add at least one field before adding rows.",
                                QMessageBox.Icon.Warning)
            return
        row = self.state.add_row()
        new_index = len(self.state.rows) - 1
        self.table.setRowCount(len(self.state.rows))
        self.table.setRowHeight(new_index, ROW_HEIGHT)
        for col, value in enumerate(row):
            self._show_cell(new_index, col, value)
        self.table.scrollToBottom()
        self._update_row_count()
        self._changed()

    def set_rows(self, result_columns, rows, truncated=False):
        """Show rows read from the database (values already JSON-decoded), matched to columns by name."""
        self.state.load_rows(result_columns, rows, truncated=truncated)
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.state.rows))
        for row_index, row in enumerate(self.state.rows):
            self.table.setRowHeight(row_index, ROW_HEIGHT)
            for col_index, value in enumerate(row):
                self._show_cell(row_index, col_index, value)
        fit_columns(self.table)
        self._update_row_count(truncated)
        self._show_pending(self.state.has_changes())
        self._show_problems()
        self._sync_value_panel()

    # ---------------- Value panel ----------------
    def showEvent(self, event):
        super().showEvent(event)
        self.value_btn.setChecked(TableDetailsPage.value_panel_open)  # as it was left on another table

    def _on_value_toggled(self, visible):
        TableDetailsPage.value_panel_open = visible
        if not visible:
            self.value_panel.hide()
            return
        self.value_panel.reveal()
        self._sync_value_panel()

    def open_value_panel(self):
        """Shift+Enter, or a double-click on a value its cell cannot edit: the whole value, ready to edit"""
        self.value_btn.setChecked(True)
        self._sync_value_panel()
        self.value_panel.focus_editor()

    def _on_cell_double_clicked(self, row, col):
        item = self.table.item(row, col)
        if item is not None and not item.flags() & Qt.ItemFlag.ItemIsEditable:
            self.open_value_panel()

    def _sync_value_panel(self):
        """Show the current cell in the value panel, when it is open"""
        if self.value_panel.isHidden():
            return
        row, col = self.table.currentRow(), self.table.currentColumn()
        self._panel_problem = None
        if not (0 <= row < len(self.state.rows) and 0 <= col < len(self.state.columns)):
            self._panel_cell = None
            self.value_panel.show_nothing()
            return
        self._panel_cell = (row, col)
        column = self.state.columns[col]
        cut = self._value_cut(row, col)
        if cut:
            note = "only these were read, so it is read-only"
        else:
            note = "" if self.state.editable else "views are read-only"
        self.value_panel.show_value(column[0], column[1], self.state.rows[row][col], where=f"row {row + 1}",
                                    editable=self.state.editable and not cut, note=note)

    def _on_panel_edited(self, text):
        """Typed in the value panel: taken at once, as a value typed in the cell is when it is left"""
        if self._panel_cell is None:
            return
        row, col = self._panel_cell
        notice, self.cell_notice = self.cell_notice, ""  # a value taken clears the note of one that was not
        self._panel_problem = self._take_value(row, col, text)
        if self._panel_problem:
            self.cell_notice = notice
            self.value_panel.set_problem(f"{self.state.columns[col][0]} {self._panel_problem} - not taken")

    def _on_panel_left(self):
        """The value panel was left with text its column cannot hold: as in a cell, the value was not taken"""
        if self._panel_problem and self._panel_cell is not None:
            self.cell_notice = self._not_taken(self._panel_cell[1], self._panel_problem)
            self._show_problems()
            self._sync_value_panel()  # back to what the cell holds

    # ---------------- Changes ----------------
    def _changed(self):
        self._show_pending(self.state.has_changes())
        self._show_problems()
        self.changes_made.emit()

    def _show_problems(self):
        lines = ([self.cell_notice] if self.cell_notice else []) + self.state.problems()
        self.problems_label.setText("\n".join(lines))
        self.problems_label.setVisible(bool(lines))

    def _show_pending(self, pending):
        self.pending_label.setVisible(pending)
        self.discard_btn.setVisible(pending)

    def _update_row_count(self, truncated=False):
        count = len(self.state.rows)
        if truncated:
            self.row_count_label.setText(f"first {count} rows")
        else:
            self.row_count_label.setText(f"{count} row{'s' if count != 1 else ''}")

    def keyPressEvent(self, event):
        if event.key() not in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):  # a Mac's delete key is Backspace
            super().keyPressEvent(event)
            return
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows or not self.state.editable:
            return
        if not confirm(self, "Delete Row(s)", "Do you want to delete the selected row(s)?"):
            return
        self.state.delete_rows(selected_rows)
        for row in reversed(selected_rows):
            self.table.removeRow(row)
        self._update_row_count()
        self._changed()
        self._sync_value_panel()

    def go_back(self):
        self.stacked.setCurrentIndex(0)


def _looks_numeric(text):
    return text.replace(".", "", 1).lstrip("-").isdigit()
