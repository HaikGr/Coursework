import re

from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat

from dbmanager.ui.common.preferences import changes
from dbmanager.ui.common.theme import color


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the query editor, in the colours of the theme (it highlights the text again
    when the theme changes)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        self._make_rules()
        changes.changed.connect(self._theme_changed)

    def _make_rules(self):
        self.highlighting_rules = []

        # SQL Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(color("code_keyword"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
            "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "DISTINCT",
            "AS", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS", "NULL",
            "ASC", "DESC", "SUM", "AVG", "COUNT", "MIN", "MAX"
        ]
        for word in keywords:
            self.highlighting_rules.append((f"\\b{word}\\b", keyword_format))

        # Table names
        table_format = QTextCharFormat()
        table_format.setForeground(color("code_table"))
        self.highlighting_rules.append(("\\b\\w+(?=\\.)", table_format))

        # Field names (after dot)
        field_format = QTextCharFormat()
        field_format.setForeground(color("code_field"))
        self.highlighting_rules.append(("\\.\\w+", field_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(color("code_number"))
        self.highlighting_rules.append(("\\b[0-9]+\\b", number_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(color("code_string"))
        self.highlighting_rules.append(("'[^']*'", string_format))

        # Operators
        operator_format = QTextCharFormat()
        operator_format.setForeground(color("code_operator"))
        self.highlighting_rules.append(("[<>=!]+", operator_format))

    def _theme_changed(self):
        self._make_rules()
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), fmt)
