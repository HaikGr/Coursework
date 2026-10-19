import re

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the query editor"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # SQL Keywords - Purple
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C792EA"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
            "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "DISTINCT",
            "AS", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS", "NULL",
            "ASC", "DESC", "SUM", "AVG", "COUNT", "MIN", "MAX"
        ]
        for word in keywords:
            self.highlighting_rules.append((f"\\b{word}\\b", keyword_format))

        # Table names - Blue
        table_format = QTextCharFormat()
        table_format.setForeground(QColor("#82AAFF"))
        self.highlighting_rules.append(("\\b\\w+(?=\\.)", table_format))

        # Field names (after dot) - Green
        field_format = QTextCharFormat()
        field_format.setForeground(QColor("#C3E88D"))
        self.highlighting_rules.append(("\\.\\w+", field_format))

        # Numbers - Orange
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#F78C6C"))
        self.highlighting_rules.append(("\\b[0-9]+\\b", number_format))

        # Strings - Yellow
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#FFCB6B"))
        self.highlighting_rules.append(("'[^']*'", string_format))

        # Operators - Red
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#FF5370"))
        self.highlighting_rules.append(("[<>=!]+", operator_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), fmt)
