from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget
)

from dbmanager.api import ApiError
from dbmanager.db import DatabaseError
from dbmanager.model.query import QueryModel
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.message_box import show_styled_message
from dbmanager.ui.common.style import MONOSPACE, shortcut_text
from dbmanager.ui.query.field_tag import ColumnTag, filter_chip, join_chip
from dbmanager.ui.query.filter_dialog import FilterDialog
from dbmanager.ui.query.highlighter import SQLHighlighter
from dbmanager.ui.query.join_dialog import JoinDialog
from dbmanager.ui.query.results_window import QueryResultsWindow

# Ctrl+Enter runs; on a Mac Qt reads Ctrl as Cmd, so it is Cmd+Enter there
RUN_KEYS = ("Ctrl+Return", "Ctrl+Enter")
_NEXT_SORT = {None: "ASC", "ASC": "DESC", "DESC": None}

_HEADER_BUTTON = """
    QPushButton {
        background-color: #334155;
        color: #cbd5e1;
        border: none;
        border-radius: 4px;
        font-size: 10px;
        padding: 0 8px;
    }
    QPushButton:hover { background-color: #475569; color: #f1f5f9; }
"""
_HINT_STYLE = "QLabel { color: #64748b; font-size: 10px; background: transparent; padding: 2px 2px 6px 2px; }"


def _clear_layout(layout):
    while layout.count():
        widget = layout.takeAt(0).widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()


class SQLQueryBuilder(QWidget):
    """The side panel: the SQL that runs, and the query built on the diagram - its columns and its filters.

    The query itself is a QueryModel; the panel shows it and changes it. query_changed tells the diagram which
    fields to mark and the toolbar which column is selected. The SQL can still be edited by hand: it is only
    written over when the built query changes."""
    query_changed = pyqtSignal()
    script_executed = pyqtSignal(list)  # one result per statement, after a successful Run
    discard_requested = pyqtSignal()  # the user wants the unsaved changes thrown away

    def __init__(self, db=None):
        super().__init__()
        self.db = db  # DatabaseClient: runs the SQL on the database itself, from this computer
        self.connection = None  # database the query runs against (set by the sidebar)
        self.change_statements = []  # SQL that saves the edits made in the table editor
        self.model = QueryModel()
        self.builder_query = ""  # SELECT built from the model
        self.warnings = []
        self.selected_key = None  # (table, column) the toolbar's aggregate buttons act on
        # Set by the sidebar: what the database would refuse in the unsaved changes, checked before a run
        self.check_before_run = lambda: []
        # Set by the diagram: {table: [(field, type)]} of the tables on it, which Join… offers
        self.table_columns = lambda: {}

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)
        self.setFixedWidth(300)

        # Header
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #1d4ed8);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)

        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.2); border-radius: 6px; }")
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("</>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("QLabel { color: white; font-size: 12px; font-weight: bold; background: transparent; "
                                 "}")
        icon_layout.addWidget(icon_label)
        header_layout.addWidget(icon_container)

        text_container = QWidget()
        text_container.setStyleSheet("QWidget { background: transparent; }")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title = QLabel("SQL Query Builder")
        title.setStyleSheet("QLabel { color: white; font-size: 13px; font-weight: 700; background: transparent; }")
        text_layout.addWidget(title)
        subtitle = QLabel("Visual query construction")
        subtitle.setStyleSheet("QLabel { color: rgba(255,255,255,0.7); font-size: 9px; background: transparent; }")
        text_layout.addWidget(subtitle)
        header_layout.addWidget(text_container)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Main content area
        content = QWidget()
        content.setStyleSheet("QWidget { background-color: #0f172a; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # Database the query will run against
        self.connection_label = QLabel()
        self.connection_label.setWordWrap(True)
        self.connection_label.setStyleSheet("QLabel { color: #94a3b8; font-size: 10px; background: transparent; }")
        content_layout.addWidget(self.connection_label)

        # "N unsaved changes" with the way to throw them away next to it
        self.changes_bar = QWidget()
        self.changes_bar.setStyleSheet("QWidget { background: transparent; }")
        changes_layout = QHBoxLayout(self.changes_bar)
        changes_layout.setContentsMargins(0, 0, 0, 0)
        changes_layout.setSpacing(6)
        self.changes_label = QLabel()
        self.changes_label.setWordWrap(True)
        self.changes_label.setStyleSheet("QLabel { color: #fbbf24; font-size: 10px; font-weight: 600; "
                                         "background: transparent; }")
        changes_layout.addWidget(self.changes_label, stretch=1)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.setFixedHeight(22)
        self.discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard_btn.setToolTip("Throw away every change that has not been run yet")
        self.discard_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #991b1b; color: #fee2e2; }
        """)
        self.discard_btn.clicked.connect(self.discard_requested.emit)
        changes_layout.addWidget(self.discard_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.changes_bar.hide()
        content_layout.addWidget(self.changes_bar)

        # SQL Preview - Auto-scales with content (editable, so generated SQL can be adjusted before running)
        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e293b;
                color: #e2e8f0;
                font-family: {MONOSPACE};
                font-size: 11px;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid #334155;
            }}
            QScrollBar:vertical {{ background: #1e293b; width: 6px; border-radius: 3px; }}
            QScrollBar::handle:vertical {{ background: #475569; border-radius: 3px; min-height: 20px; }}
            QScrollBar:horizontal {{ background: #1e293b; height: 6px; border-radius: 3px; }}
            QScrollBar::handle:horizontal {{ background: #475569; border-radius: 3px; min-width: 20px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
        """)
        self.sql_editor.setPlaceholderText("Pick fields or type SQL here")
        self.sql_editor.setAcceptRichText(False)
        self.sql_editor.setMinimumHeight(80)
        self.sql_editor.setMaximumHeight(260)
        # documentSizeChanged also fires when the text re-wraps to the editor's final width
        self.sql_editor.document().documentLayout().documentSizeChanged.connect(self._adjust_editor_height)
        self.highlighter = SQLHighlighter(self.sql_editor.document())
        content_layout.addWidget(self.sql_editor)

        # What is odd about the query: tables that are not linked, a SUM of text...
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("""
            QLabel {
                color: #fde68a; background-color: #422006; border-left: 3px solid #f59e0b;
                border-radius: 4px; font-size: 10px; padding: 6px 8px;
            }
        """)
        self.warning_label.hide()
        content_layout.addWidget(self.warning_label)
        # A table nothing joins to the others: choose how, right here
        self.join_unjoined_btn = QPushButton()
        self.join_unjoined_btn.setFixedHeight(26)
        self.join_unjoined_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.join_unjoined_btn.setStyleSheet("""
            QPushButton { background-color: #0f766e; color: #f0fdfa; border: none; border-radius: 6px;
                          font-size: 11px; font-weight: 600; padding: 0 10px; }
            QPushButton:hover { background-color: #0d9488; }
        """)
        self.join_unjoined_btn.clicked.connect(
            lambda: self.edit_join(right_table=self.model.unjoined[0] if self.model.unjoined else None))
        self.join_unjoined_btn.hide()
        content_layout.addWidget(self.join_unjoined_btn)

        # Columns and filters, scrolled together
        lists = QWidget()
        lists.setStyleSheet("QWidget { background: transparent; }")
        lists_layout = QVBoxLayout(lists)
        lists_layout.setContentsMargins(0, 0, 4, 0)
        lists_layout.setSpacing(4)

        self.columns_title, columns_header = self._section_header()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(20)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(_HEADER_BUTTON)
        clear_btn.setToolTip("Start the query again: no columns, filters or options.\n"
                             "Unsaved table changes stay - use Discard to drop them.")
        clear_btn.clicked.connect(self.clear_query)
        columns_header.layout().addWidget(clear_btn)
        lists_layout.addWidget(columns_header)
        self.columns_hint = QLabel("Click the circle at the end of a field on the diagram to add it here - "
                                   "or right-click the field for more.")
        self.columns_hint.setWordWrap(True)
        self.columns_hint.setStyleSheet(_HINT_STYLE)
        lists_layout.addWidget(self.columns_hint)
        self.columns_layout = QVBoxLayout()
        self.columns_layout.setSpacing(4)
        lists_layout.addLayout(self.columns_layout)

        self.joins_title, joins_header = self._section_header()
        self.add_join_btn = QPushButton("+ Join")
        self.add_join_btn.setFixedHeight(20)
        self.add_join_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_join_btn.setStyleSheet(_HEADER_BUTTON)
        self.add_join_btn.setToolTip("Join two tables on fields of your choice, or keep the rows that match nothing\n"
                                     "(LEFT JOIN) - for this query only, the database is not changed")
        self.add_join_btn.clicked.connect(lambda: self.edit_join())
        joins_header.layout().addWidget(self.add_join_btn)
        lists_layout.addSpacing(6)
        lists_layout.addWidget(joins_header)
        self.joins_hint = QLabel("Tables are joined along the links of the diagram. + Join joins them on other "
                                 "fields, or keeps rows without a match.")
        self.joins_hint.setWordWrap(True)
        self.joins_hint.setStyleSheet(_HINT_STYLE)
        lists_layout.addWidget(self.joins_hint)
        self.joins_layout = QVBoxLayout()
        self.joins_layout.setSpacing(4)
        lists_layout.addLayout(self.joins_layout)

        self.filters_title, filters_header = self._section_header()
        self.match_btn = QPushButton()
        self.match_btn.setFixedHeight(20)
        self.match_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.match_btn.setStyleSheet(_HEADER_BUTTON)
        self.match_btn.setToolTip("All: a row must pass every filter (AND).\nAny: passing one of them is enough (OR).")
        self.match_btn.clicked.connect(lambda: self.set_match_any(not self.model.match_any))
        filters_header.layout().addWidget(self.match_btn)
        lists_layout.addSpacing(6)
        lists_layout.addWidget(filters_header)
        self.filters_hint = QLabel("Right-click a field on the diagram and choose Add filter… "
                                   "to keep only the rows you need.")
        self.filters_hint.setWordWrap(True)
        self.filters_hint.setStyleSheet(_HINT_STYLE)
        lists_layout.addWidget(self.filters_hint)
        self.filters_layout = QVBoxLayout()
        self.filters_layout.setSpacing(4)
        lists_layout.addLayout(self.filters_layout)
        lists_layout.addStretch()

        lists_scroll = QScrollArea()
        lists_scroll.setWidgetResizable(True)
        lists_scroll.setFrameShape(QFrame.Shape.NoFrame)
        lists_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lists_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1e293b; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
        """)
        lists_scroll.setWidget(lists)
        content_layout.addWidget(lists_scroll, stretch=3)

        run_btn = QPushButton("▶  Run Query")
        run_btn.setFixedHeight(38)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setToolTip(f"Run everything in the editor above ({shortcut_text(RUN_KEYS[0])})")
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        run_btn.clicked.connect(self.run_query)
        content_layout.addWidget(run_btn)
        for keys in RUN_KEYS:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.run_query)

        self.copy_btn = QPushButton("Copy Query")
        self.copy_btn.setFixedHeight(34)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #e2e8f0;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_query)
        content_layout.addWidget(self.copy_btn)
        self._copied_timer = QTimer(self)  # "Copied ✓" turns back into "Copy Query"
        self._copied_timer.setSingleShot(True)
        self._copied_timer.timeout.connect(lambda: self.copy_btn.setText("Copy Query"))

        main_layout.addWidget(content)
        self.set_connection(None)
        self._refresh(render=True)

    @staticmethod
    def _section_header():
        header = QWidget()
        header.setStyleSheet("QWidget { background: transparent; }")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        title = QLabel()
        title.setStyleSheet("QLabel { color: #fbbf24; font-size: 11px; font-weight: 700; background: transparent; }")
        layout.addWidget(title)
        layout.addStretch()
        return title, header

    def _adjust_editor_height(self):
        """Auto-scale SQL editor height based on content"""
        doc_height = self.sql_editor.document().size().height()
        new_height = max(80, min(260, int(doc_height + 24)))
        self.sql_editor.setFixedHeight(new_height)

    # ---------------- The database ----------------
    def _db_type(self):
        return self.connection["dbType"] if self.connection else None

    def set_connection(self, connection):
        """Select the database (API connection dict, or None) the query runs against"""
        self.connection = connection
        if connection:
            self.connection_label.setText(f"Database: {connection['dbName']}  ({connection['dbType']})")
        else:
            self.connection_label.setText("No database selected - pick one in the sidebar")
        self._refresh()  # names are quoted the way this database reads them

    def set_connections(self, connections):
        """The PK-FK links drawn on the diagram: [(pk row, fk row, relation)]. Tables are joined along them."""
        self.model.links = [(pk.table_card.table_name, pk.field_data[0], fk.table_card.table_name, fk.field_data[0])
                            for pk, fk, _ in connections]
        self._changed()

    @property
    def table_connections(self):
        return self.model.links

    # ---------------- Columns ----------------
    def add_field(self, table_name, field_name, type_name=""):
        """Add a column to the query and select it; False when it is in the query already"""
        entry = self.model.add_column(table_name, field_name, type_name)
        if entry is None:
            return False
        self.selected_key = entry.key
        self._changed()
        return True

    def remove_field(self, table_name, field_name):
        """Take a column out of the query (its sort goes with it; its filters stay)"""
        if not self.model.remove_column(table_name, field_name):
            return False
        if self.selected_key == (table_name, field_name):
            self.selected_key = self.model.columns[-1].key if self.model.columns else None
        self._changed()
        return True

    def toggle_field(self, table_name, field_name, type_name=""):
        """Add the field if it is not in the query, remove it otherwise; True when it was added"""
        if self.is_field_selected(table_name, field_name):
            self.remove_field(table_name, field_name)
            return False
        self.add_field(table_name, field_name, type_name)
        return True

    def is_field_selected(self, table_name, field_name):
        return self.model.column(table_name, field_name) is not None

    def selected_column(self):
        """The column the toolbar acts on, or None"""
        return self.model.column(*self.selected_key) if self.selected_key else None

    def select_column(self, key):
        if key != self.selected_key:
            self.selected_key = key
            self._changed()

    def set_aggregate(self, aggregate):
        """From the toolbar: summarise the selected column ("" or None: show it as it is). False with no column."""
        entry = self.selected_column()
        if entry is None:
            return False
        self.model.set_aggregate(entry.table, entry.column, aggregate or None)
        self._changed()
        return True

    def set_column_aggregate(self, table_name, field_name, aggregate, type_name=""):
        """Summarise a column, adding it to the query first if needed"""
        self.model.add_column(table_name, field_name, type_name)
        self.model.set_aggregate(table_name, field_name, aggregate)
        self.selected_key = (table_name, field_name)
        self._changed()

    def set_column_sort(self, table_name, field_name, direction, type_name=""):
        """Sort by a column ("ASC", "DESC" or None), adding it to the query first if needed"""
        self.model.add_column(table_name, field_name, type_name)
        self.model.set_sort(table_name, field_name, direction)
        self._changed()

    def _on_aggregate_chosen(self, key, aggregate):
        self.model.set_aggregate(*key, aggregate)
        self.selected_key = key
        self._changed()

    def _cycle_sort(self, key):
        self.model.set_sort(*key, _NEXT_SORT[self.model.column(*key).sort])
        self.selected_key = key
        self._changed()

    # ---------------- Options ----------------
    def set_count_rows(self, on):
        self.model.count_rows = bool(on)
        self._changed()

    def set_distinct(self, on):
        self.model.distinct = bool(on)
        self._changed()

    def set_limit(self, rows):
        self.model.limit = max(0, int(rows))
        self._changed()

    def set_match_any(self, on):
        self.model.match_any = bool(on)
        self._changed()

    # ---------------- Filters ----------------
    def add_filter(self, condition):
        self.model.add_filter(condition)
        self._changed()

    def edit_filter(self, table_name, field_name, type_name="", index=None):
        """Ask for a new filter on a column, or a change to the one at index. True when the query changed."""
        existing = self.model.filters[index] if index is not None else None
        entry = self.model.column(table_name, field_name)
        dialog = FilterDialog(self.window(), table_name, field_name, type_name, self._db_type(), existing,
                              aggregate=entry.aggregate if entry else None)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        if dialog.removed:
            self.model.remove_filter(index)
        elif index is None:
            self.model.add_filter(dialog.result)
        else:
            self.model.replace_filter(index, dialog.result)
        self._changed()
        return True

    def _edit_filter_at(self, index):
        condition = self.model.filters[index]
        self.edit_filter(condition.table, condition.column, condition.type_name, index)

    def remove_filter(self, index):
        self.model.remove_filter(index)
        self._changed()

    def remove_filters_on(self, table_name, field_name):
        self.model.remove_filters_on(table_name, field_name)
        self._changed()

    # ---------------- Joins ----------------
    def edit_join(self, index=None, right_table=None):
        """Ask for a join of the query (or a change to the one at index). True when the query changed."""
        tables = self.table_columns()
        if len(tables) < 2:
            show_styled_message(self, "Join Tables", "There are no two tables on the diagram to join.",
                                QMessageBox.Icon.Warning)
            return False
        existing = self.model.joins[index] if index is not None else None
        dialog = JoinDialog(self.window(), tables, self.model.tables(), self._db_type(), existing=existing,
                            right_table=right_table)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        if dialog.removed:
            self.model.remove_join(index)
        elif index is None:
            self.model.add_join(dialog.result)
        else:
            self.model.replace_join(index, dialog.result)
        self._changed()
        return True

    def add_join(self, join):
        self.model.add_join(join)
        self._changed()

    def remove_join(self, index):
        self.model.remove_join(index)
        self._changed()

    # ---------------- The schema changed ----------------
    def rename_column(self, table_name, old_name, new_name):
        self.model.rename_column(table_name, old_name, new_name)
        if self.selected_key == (table_name, old_name):
            self.selected_key = (table_name, new_name)
        self._changed()

    def drop_column(self, table_name, field_name):
        self.model.drop_column(table_name, field_name)
        self._changed()

    def drop_table(self, table_name):
        self.model.drop_table(table_name)
        self._changed()

    def keep_only(self, known):
        """After the database was read again: forget what it no longer has ({table: {column, ...}})"""
        if self.model.keep_only(known):
            self._changed()

    # ---------------- Showing the query ----------------
    def _changed(self):
        self._refresh()
        self.query_changed.emit()

    def _refresh(self, render=False):
        """Build the SQL again and show the columns and filters. The editor is written over only when the
        built query is or was something: SQL typed by hand stays while nothing is picked."""
        previous = self.builder_query
        self.builder_query, self.warnings = self.model.build(self._db_type())
        if self.selected_key and self.model.column(*self.selected_key) is None:
            self.selected_key = None
        if render or self.builder_query or previous:
            self._render_editor()
        self.warning_label.setText("\n\n".join(self.warnings))
        self.warning_label.setVisible(bool(self.warnings))
        if self.model.unjoined:
            self.join_unjoined_btn.setText(f"Join {self.model.unjoined[0]}…")
        self.join_unjoined_btn.setVisible(bool(self.model.unjoined))
        self._render_lists()

    def _render_lists(self):
        _clear_layout(self.columns_layout)
        for entry in self.model.columns:
            tag = ColumnTag(entry, grouped=self.model.is_group_key(*entry.key),
                            rank=self.model.sort_rank(*entry.key), is_selected=entry.key == self.selected_key)
            tag.selected.connect(self.select_column)
            tag.aggregate_chosen.connect(self._on_aggregate_chosen)
            tag.sort_clicked.connect(self._cycle_sort)
            tag.remove_clicked.connect(lambda key: self.remove_field(*key))
            self.columns_layout.addWidget(tag)
        extra = "  +  row count" if self.model.count_rows and self.model.columns else ""
        self.columns_title.setText(f"COLUMNS ({len(self.model.columns)}){extra}")
        self.columns_hint.setVisible(not self.model.columns)

        _clear_layout(self.joins_layout)
        for index, join in enumerate(self.model.joins):
            chip = join_chip(index, join)
            chip.edit_clicked.connect(lambda i: self.edit_join(i))
            chip.remove_clicked.connect(self.remove_join)
            self.joins_layout.addWidget(chip)
        self.joins_title.setText(f"JOINS ({len(self.model.joins)})")
        self.joins_hint.setVisible(not self.model.joins)

        _clear_layout(self.filters_layout)
        for index, condition in enumerate(self.model.filters):
            chip = filter_chip(index, condition)
            chip.edit_clicked.connect(self._edit_filter_at)
            chip.remove_clicked.connect(self.remove_filter)
            self.filters_layout.addWidget(chip)
        self.filters_title.setText(f"FILTERS ({len(self.model.filters)})")
        self.filters_hint.setVisible(not self.model.filters)
        self.match_btn.setText("Match any" if self.model.match_any else "Match all")
        self.match_btn.setVisible(len(self.model.filters) > 1)

    def set_change_script(self, statements):
        """Show the SQL that saves the table editor's edits; Run executes it before any SELECT"""
        self.change_statements = list(statements)
        count = len(self.change_statements)
        self.changes_label.setText(f"{count} unsaved change{'s' if count != 1 else ''} - "
                                   "click Run Query to save them to the database")
        self.changes_bar.setVisible(count > 0)
        self._render_editor()

    def _render_editor(self):
        parts = [statement + ";" for statement in self.change_statements]
        if self.builder_query:
            parts.append(self.builder_query)
        self.sql_editor.setPlainText("\n\n".join(parts))

    def clear_query(self):
        self.model.clear()
        self.selected_key = None
        self._refresh(render=True)
        self.query_changed.emit()

    # ---------------- Copy and run ----------------
    def copy_query(self):
        query = self.sql_editor.toPlainText()
        if query:
            QApplication.clipboard().setText(query)
            self.copy_btn.setText("Copied ✓")
            self._copied_timer.start(1500)

    def run_query(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            show_styled_message(self, "Run Query", "There is no query to run yet.", QMessageBox.Icon.Warning)
            return
        if not self.db or not self.connection:
            show_styled_message(self, "Run Query", "Select a database in the sidebar first.",
                                QMessageBox.Icon.Warning)
            return
        problems = self.check_before_run() if self.change_statements else []
        if problems:
            show_styled_message(self, "Not Run Yet", "The database would refuse these changes - nothing was run:\n\n• "
                                + "\n• ".join(problems), QMessageBox.Icon.Warning)
            return
        connection = self.connection
        try:
            with busy_cursor():
                result = self.db.run_script(connection, sql)
        except (DatabaseError, ApiError) as error:
            if not getattr(error, "cancelled", False):
                show_styled_message(self, "Query Failed", str(error), QMessageBox.Icon.Critical)
            return
        result = result or {}
        results = result.get("results") or []
        QueryResultsWindow(results, result.get("durationMs", 0), connection["dbName"], self).exec()
        self.script_executed.emit(results)
