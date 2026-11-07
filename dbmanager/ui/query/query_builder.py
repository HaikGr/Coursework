from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget
)

from dbmanager.api import ApiError
from dbmanager.db import DatabaseError
from dbmanager.i18n import tr, trn
from dbmanager.model.query import QueryModel
from dbmanager.ui.common.busy import busy_cursor
from dbmanager.ui.common.live import bind
from dbmanager.ui.common.message_box import show_styled_message
from dbmanager.ui.common.preferences import changes
from dbmanager.ui.common.style import MONOSPACE, shortcut_text
from dbmanager.ui.common.theme import style
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
        background-color: @surface_raised;
        color: @text_secondary;
        border: none;
        border-radius: 4px;
        font-size: 10px;
        padding: 0 8px;
    }
    QPushButton:hover { background-color: @surface_pressed; color: @text; }
"""
_HINT_STYLE = "QLabel { color: @text_muted; font-size: 10px; background: transparent; padding: 2px 2px 6px 2px; }"


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
        style(header, """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 @brand, stop:1 @accent_pressed);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)

        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        style(icon_container, "QFrame { background-color: @brand_hover; border-radius: 6px; }")
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("</>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        style(icon_label, "QLabel { color: @on_brand; font-size: 12px; font-weight: bold; background: transparent; }")
        icon_layout.addWidget(icon_label)
        header_layout.addWidget(icon_container)

        text_container = QWidget()
        style(text_container, "QWidget { background: transparent; }")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title = QLabel()
        bind(title.setText, "query.builder.title")
        style(title, "QLabel { color: @on_brand; font-size: 13px; font-weight: 700; background: transparent; }")
        text_layout.addWidget(title)
        subtitle = QLabel()
        bind(subtitle.setText, "query.builder.subtitle")
        style(subtitle, "QLabel { color: @on_brand_muted; font-size: 9px; background: transparent; }")
        text_layout.addWidget(subtitle)
        header_layout.addWidget(text_container)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Main content area
        content = QWidget()
        style(content, "QWidget { background-color: @surface; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # Database the query will run against
        self.connection_label = QLabel()
        self.connection_label.setWordWrap(True)
        style(self.connection_label, "QLabel { color: @text_muted; font-size: 10px; background: transparent; }")
        content_layout.addWidget(self.connection_label)

        # "N unsaved changes" with the way to throw them away under it: the button's name is long in some
        # languages, and beside it the text would have no room left
        self.changes_bar = QWidget()
        style(self.changes_bar, "QWidget { background: transparent; }")
        changes_layout = QVBoxLayout(self.changes_bar)
        changes_layout.setContentsMargins(0, 0, 0, 0)
        changes_layout.setSpacing(4)
        self.changes_label = QLabel()
        self.changes_label.setWordWrap(True)
        style(self.changes_label, "QLabel { color: @warning_text; font-size: 10px; font-weight: 600; "
                                  "background: transparent; }")
        changes_layout.addWidget(self.changes_label)
        self.discard_btn = QPushButton()
        bind(self.discard_btn.setText, "common.action.discard")
        self.discard_btn.setFixedHeight(22)
        self.discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bind(self.discard_btn.setToolTip, "query.builder.discard_tip")
        style(self.discard_btn, """
            QPushButton {
                background-color: @danger_subtle;
                color: @danger_text;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: @danger; color: @on_danger; }
        """)
        self.discard_btn.clicked.connect(self.discard_requested.emit)
        changes_layout.addWidget(self.discard_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.changes_bar.hide()
        content_layout.addWidget(self.changes_bar)

        # SQL Preview - Auto-scales with content (editable, so generated SQL can be adjusted before running)
        self.sql_editor = QTextEdit()
        style(self.sql_editor, f"""
            QTextEdit {{
                background-color: @code_background;
                color: @code_text;
                font-family: {MONOSPACE};
                font-size: 11px;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid @border;
                selection-background-color: @selection;
                selection-color: @on_selection;
            }}
            QScrollBar:vertical {{ background: @code_background; width: 6px; border-radius: 3px; }}
            QScrollBar::handle:vertical {{ background: @scrollbar; border-radius: 3px; min-height: 20px; }}
            QScrollBar:horizontal {{ background: @code_background; height: 6px; border-radius: 3px; }}
            QScrollBar::handle:horizontal {{ background: @scrollbar; border-radius: 3px; min-width: 20px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
        """)
        bind(self.sql_editor.setPlaceholderText, "query.builder.editor_placeholder")
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
        style(self.warning_label, """
            QLabel {
                color: @warning_text; background-color: @warning_subtle; border-left: 3px solid @warning;
                border-radius: 4px; font-size: 10px; padding: 6px 8px;
            }
        """)
        self.warning_label.hide()
        content_layout.addWidget(self.warning_label)
        # A table nothing joins to the others: choose how, right here
        self.join_unjoined_btn = QPushButton()
        self.join_unjoined_btn.setFixedHeight(26)
        self.join_unjoined_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(self.join_unjoined_btn, """
            QPushButton { background-color: @option; color: @on_option; border: none; border-radius: 6px;
                          font-size: 11px; font-weight: 600; padding: 0 10px; }
            QPushButton:hover { background-color: @option_hover; }
        """)
        self.join_unjoined_btn.clicked.connect(
            lambda: self.edit_join(right_table=self.model.unjoined[0] if self.model.unjoined else None))
        self.join_unjoined_btn.hide()
        content_layout.addWidget(self.join_unjoined_btn)

        # Columns and filters, scrolled together
        lists = QWidget()
        style(lists, "QWidget { background: transparent; }")
        lists_layout = QVBoxLayout(lists)
        lists_layout.setContentsMargins(0, 0, 4, 0)
        lists_layout.setSpacing(4)

        self.columns_title, columns_header = self._section_header()
        clear_btn = QPushButton()
        bind(clear_btn.setText, "common.clear")
        clear_btn.setFixedHeight(20)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(clear_btn, _HEADER_BUTTON)
        bind(clear_btn.setToolTip, lambda: tr("query.builder.clear_tip", discard=tr("common.action.discard")))
        clear_btn.clicked.connect(self.clear_query)
        columns_header.layout().addWidget(clear_btn)
        lists_layout.addWidget(columns_header)
        self.columns_hint = QLabel()
        bind(self.columns_hint.setText, "query.builder.columns_hint")
        self.columns_hint.setWordWrap(True)
        style(self.columns_hint, _HINT_STYLE)
        lists_layout.addWidget(self.columns_hint)
        self.columns_layout = QVBoxLayout()
        self.columns_layout.setSpacing(4)
        lists_layout.addLayout(self.columns_layout)

        self.joins_title, joins_header = self._section_header()
        self.add_join_btn = QPushButton()
        bind(self.add_join_btn.setText, "query.builder.add_join")
        self.add_join_btn.setFixedHeight(20)
        self.add_join_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(self.add_join_btn, _HEADER_BUTTON)
        bind(self.add_join_btn.setToolTip, "query.builder.add_join_tip")
        self.add_join_btn.clicked.connect(lambda: self.edit_join())
        joins_header.layout().addWidget(self.add_join_btn)
        lists_layout.addSpacing(6)
        lists_layout.addWidget(joins_header)
        self.joins_hint = QLabel()
        bind(self.joins_hint.setText, lambda: tr("query.builder.joins_hint", add_join=tr("query.builder.add_join")))
        self.joins_hint.setWordWrap(True)
        style(self.joins_hint, _HINT_STYLE)
        lists_layout.addWidget(self.joins_hint)
        self.joins_layout = QVBoxLayout()
        self.joins_layout.setSpacing(4)
        lists_layout.addLayout(self.joins_layout)

        self.filters_title, filters_header = self._section_header()
        self.match_btn = QPushButton()
        self.match_btn.setFixedHeight(20)
        self.match_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(self.match_btn, _HEADER_BUTTON)
        bind(self.match_btn.setToolTip, "query.builder.match_tip")
        self.match_btn.clicked.connect(lambda: self.set_match_any(not self.model.match_any))
        filters_header.layout().addWidget(self.match_btn)
        lists_layout.addSpacing(6)
        lists_layout.addWidget(filters_header)
        self.filters_hint = QLabel()
        bind(self.filters_hint.setText, "query.builder.filters_hint")
        self.filters_hint.setWordWrap(True)
        style(self.filters_hint, _HINT_STYLE)
        lists_layout.addWidget(self.filters_hint)
        self.filters_layout = QVBoxLayout()
        self.filters_layout.setSpacing(4)
        lists_layout.addLayout(self.filters_layout)
        lists_layout.addStretch()

        lists_scroll = QScrollArea()
        lists_scroll.setWidgetResizable(True)
        lists_scroll.setFrameShape(QFrame.Shape.NoFrame)
        lists_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        style(lists_scroll, """
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: @surface_alt; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: @scrollbar; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
        """)
        lists_scroll.setWidget(lists)
        content_layout.addWidget(lists_scroll, stretch=3)

        run_btn = QPushButton()
        bind(run_btn.setText, lambda: f"▶  {tr('common.action.run_query')}")
        run_btn.setFixedHeight(38)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bind(run_btn.setToolTip, "query.builder.run_tip", keys=shortcut_text(RUN_KEYS[0]))
        style(run_btn, """
            QPushButton {
                background-color: @accent;
                color: @on_accent;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: @accent_hover;
            }
        """)
        run_btn.clicked.connect(self.run_query)
        content_layout.addWidget(run_btn)
        for keys in RUN_KEYS:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.run_query)

        self.copy_btn = QPushButton()
        bind(self.copy_btn.setText, "query.builder.copy")
        self.copy_btn.setFixedHeight(34)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        style(self.copy_btn, """
            QPushButton {
                background-color: @surface_raised;
                color: @text_secondary;
                border: 1px solid @border;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: @surface_pressed;
                color: @text;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_query)
        content_layout.addWidget(self.copy_btn)
        self._copied_timer = QTimer(self)  # "Copied ✓" turns back into "Copy Query"
        self._copied_timer.setSingleShot(True)
        self._copied_timer.timeout.connect(lambda: bind(self.copy_btn.setText, "query.builder.copy"))

        main_layout.addWidget(content)
        self.set_connection(None)
        self._refresh(render=True)
        changes.changed.connect(self._show_again)

    @staticmethod
    def _section_header():
        header = QWidget()
        style(header, "QWidget { background: transparent; }")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        title = QLabel()
        style(title, "QLabel { color: @warning_text; font-size: 11px; font-weight: 700; background: transparent; }")
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
            bind(self.connection_label.setText, "query.builder.database", name=connection["dbName"],
                 type=connection["dbType"])
        else:
            bind(self.connection_label.setText, "query.builder.no_database")
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
            show_styled_message(self, tr("query.join.title"), tr("query.builder.no_two_tables"),
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
            table = self.model.unjoined[0]
            bind(self.join_unjoined_btn.setText, lambda: tr("query.builder.join_table", table=table))
        self.join_unjoined_btn.setVisible(bool(self.model.unjoined))
        self._render_lists()

    def _show_again(self):
        """After a change of language or theme. The warnings and the lists are made from the model in the
        language of the moment, and the tags and chips take the theme as they are made: make them again. The
        SQL stays as it is - it may have been edited by hand."""
        self.warnings = self.model.build(self._db_type())[1]
        self.warning_label.setText("\n\n".join(self.warnings))
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
        title = ("query.builder.columns_with_row_count" if self.model.count_rows and self.model.columns
                 else "query.builder.columns")
        bind(self.columns_title.setText, title, count=len(self.model.columns))
        self.columns_hint.setVisible(not self.model.columns)

        _clear_layout(self.joins_layout)
        for index, join in enumerate(self.model.joins):
            chip = join_chip(index, join)
            chip.edit_clicked.connect(lambda i: self.edit_join(i))
            chip.remove_clicked.connect(self.remove_join)
            self.joins_layout.addWidget(chip)
        bind(self.joins_title.setText, "query.builder.joins", count=len(self.model.joins))
        self.joins_hint.setVisible(not self.model.joins)

        _clear_layout(self.filters_layout)
        for index, condition in enumerate(self.model.filters):
            chip = filter_chip(index, condition)
            chip.edit_clicked.connect(self._edit_filter_at)
            chip.remove_clicked.connect(self.remove_filter)
            self.filters_layout.addWidget(chip)
        bind(self.filters_title.setText, "query.builder.filters", count=len(self.model.filters))
        self.filters_hint.setVisible(not self.model.filters)
        bind(self.match_btn.setText, "query.builder.match_any" if self.model.match_any else "query.builder.match_all")
        self.match_btn.setVisible(len(self.model.filters) > 1)

    def set_change_script(self, statements):
        """Show the SQL that saves the table editor's edits; Run executes it before any SELECT"""
        self.change_statements = list(statements)
        count = len(self.change_statements)
        bind(self.changes_label.setText,
             lambda: trn("query.builder.unsaved_changes", count, run_query=tr("common.action.run_query")))
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
            bind(self.copy_btn.setText, "query.builder.copied")
            self._copied_timer.start(1500)

    def run_query(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            show_styled_message(self, tr("common.action.run_query"), tr("query.builder.nothing_to_run"),
                                QMessageBox.Icon.Warning)
            return
        if not self.db or not self.connection:
            show_styled_message(self, tr("common.action.run_query"), tr("query.builder.select_database"),
                                QMessageBox.Icon.Warning)
            return
        problems = self.check_before_run() if self.change_statements else []
        if problems:
            show_styled_message(self, tr("query.builder.not_run_title"),
                                tr("query.builder.refused", problems="\n• ".join(problems)), QMessageBox.Icon.Warning)
            return
        connection = self.connection
        try:
            with busy_cursor():
                result = self.db.run_script(connection, sql)
        except (DatabaseError, ApiError) as error:
            if not getattr(error, "cancelled", False):
                show_styled_message(self, tr("query.builder.failed_title"), str(error), QMessageBox.Icon.Critical)
            return
        result = result or {}
        results = result.get("results") or []
        QueryResultsWindow(results, result.get("durationMs", 0), connection["dbName"], self).exec()
        self.script_executed.emit(results)
