from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from dbmanager.api import ApiError
from dbmanager.ui.common.icons import app_icon
from dbmanager.ui.common.transitions import WindowTransition
from dbmanager.ui.dashboard.side_bar import SideBar
from dbmanager.ui.dashboard.tool_bar import Toolbar
from dbmanager.ui.dashboard.top_bar import TopBar
from dbmanager.ui.diagram.diagram_page import DiagramPage
from dbmanager.ui.query.query_builder import SQLQueryBuilder


class DashboardWindow(QMainWindow):
    """Sidebar | toolbar over the diagram or a table page | SQL query builder."""

    def __init__(self, api, parent_window=None, geometry=None):
        super().__init__()
        self.setWindowTitle("SQL Query Builder - Dashboard")
        self.setWindowIcon(app_icon())
        self.parent_window = parent_window
        self.api = api
        self.username = api.username

        if geometry:
            self.restoreGeometry(geometry)

        self.setStyleSheet("background-color: #f5f6f7;")
        self.setMinimumSize(1200, 700)

        main_widget = QWidget()
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(main_widget)
        root_layout.addWidget(TopBar(self.username))

        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(body_layout)

        self.sql_builder = SQLQueryBuilder(api)

        # One toolbar for the diagram and every table page: the aggregate it sets is the query builder's
        self.toolbar = Toolbar()
        self.toolbar.aggregate_selected.connect(self.sql_builder.set_aggregate)
        self.sql_builder.fields_cleared.connect(self.toolbar.reset_aggregate)

        self.stacked_center = QStackedWidget()
        self.diagram_page = DiagramPage(sql_builder=self.sql_builder)
        self.stacked_center.addWidget(self.diagram_page)

        center = QWidget()
        center.setMinimumWidth(900)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.toolbar)
        center_layout.addWidget(self.stacked_center)

        # Created after the diagram page: it loads the user's databases from the server
        self.sidebar_widget = SideBar(self.stacked_center, self.diagram_page, api, self.sql_builder)
        self.sidebar_widget.logout_requested.connect(self.log_out)

        body_layout.addWidget(self.sidebar_widget)
        body_layout.addWidget(center, stretch=3)
        body_layout.addWidget(self.sql_builder, stretch=1)

        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setWindowOpacity(0.0)
            QTimer.singleShot(50, lambda: WindowTransition.fade_in(self, duration=400))

    def _end_session(self):
        try:
            self.api.logout()
        except ApiError:
            pass  # the token is dropped locally either way

    def log_out(self):
        self._end_session()
        if self.parent_window:
            WindowTransition.cross_fade(self, self.parent_window, duration=400)
        else:
            self.close()

    def closeEvent(self, event):
        # Closing the window ends the app: revoke the token instead of leaving it valid until it expires
        if self.api.signed_in:
            self._end_session()
        super().closeEvent(event)
