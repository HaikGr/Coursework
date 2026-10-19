from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


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
