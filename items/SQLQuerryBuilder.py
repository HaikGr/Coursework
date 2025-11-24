from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,QTextEdit,
    QFrame

)


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