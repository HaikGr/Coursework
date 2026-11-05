"""Splitting SQL into statements, and naming what each one does.

A small lexer, not a parser: it skips string literals, quoted identifiers and comments the way the
target dialect does, so a ';' or a keyword inside one of them is not mistaken for SQL. It decides only
where statements end and which verb leads each one - what a user may run is the database's business,
since every user signs in with a login that holds exactly their permissions.

The two client conventions for bodies that hold ';' of their own (procedures, triggers) are understood:
SQL Server's GO line, which ends a batch that is then sent whole, and MySQL's DELIMITER line, which
changes what ends a statement.
"""

import re

_VERBS_AFTER_WITH = ("SELECT", "INSERT", "UPDATE", "DELETE", "MERGE")
_GO_LINE = re.compile(r"[ \t]*GO(?:[ \t]+\d+)?[ \t]*(?:--[^\r\n]*)?(?:\r?\n|$)", re.IGNORECASE)
_DELIMITER_LINE = re.compile(r"[ \t]*DELIMITER[ \t]+(\S+)[ \t]*(?:\r?\n|$)", re.IGNORECASE)


def split_script(sql, db_type):
    """The statements of a script, in order, stripped; empty ones (or only comments) left out. On SQL Server
    a script with GO lines is split into its batches only, as SQL Server Management Studio does."""
    scanner = _Scanner(sql or "", db_type)
    scanner.scan()
    statements, start = [], 0
    for cut_start, cut_end in (scanner.go_lines or scanner.cuts) + [(len(scanner.sql), len(scanner.sql))]:
        statement = scanner.sql[start:cut_start].strip()
        if statement and _words(statement, db_type):
            statements.append(statement)
        start = cut_end
    return statements


def statement_type(statement, db_type):
    """The leading verb, upper case: SELECT, INSERT, CREATE, ... - for WITH, the verb the WITH leads to."""
    words = _words(statement, db_type)
    if not words:
        return ""
    first = words[0][0]
    if first != "WITH":
        return first
    return next((word for word, depth in words[1:] if depth == 0 and word in _VERBS_AFTER_WITH), "WITH")


def _words(sql, db_type):
    scanner = _Scanner(sql, db_type)
    scanner.scan()
    return scanner.words


class _Scanner:
    def __init__(self, sql, db_type):
        self.sql = sql
        self.db_type = db_type
        self.mysql = db_type in ("MYSQL", "MARIADB")
        self.pos = 0
        self.depth = 0
        self.words = []        # (WORD, parenthesis depth)
        self.cuts = []         # (start, end) of what ends each statement: a ';', or a DELIMITER line and the like
        self.go_lines = []     # (start, end) of SQL Server's GO lines
        self.delimiter = ";"

    def peek(self, offset=0):
        i = self.pos + offset
        return self.sql[i] if i < len(self.sql) else ""

    def scan(self):
        sql = self.sql
        while self.pos < len(sql):
            c = sql[self.pos]
            if (self.pos == 0 or sql[self.pos - 1] == "\n") and self._client_line():
                continue
            if self._starts_line_comment():
                end = len(sql)
                for stop in ("\n", "\r"):
                    found = sql.find(stop, self.pos)
                    if found >= 0:
                        end = min(end, found)
                self.pos = end
            elif c == "/" and self.peek(1) == "*":
                self._skip_block_comment()
            elif sql.startswith(self.delimiter, self.pos):
                self.cuts.append((self.pos, self.pos + len(self.delimiter)))
                self.depth = 0
                self.pos += len(self.delimiter)
            elif c == "'":
                self._skip_quoted("'", backslashes=self.mysql)
            elif c == '"':
                self._skip_quoted('"', backslashes=self.mysql)
            elif c == "`" and self.mysql:
                self._skip_quoted("`")
            elif c == "[" and self.db_type == "SQLSERVER":
                self._skip_quoted("]")
            elif c == "$" and self.db_type == "POSTGRESQL":
                self._skip_dollar_quoted()
            elif c == "(":
                self.depth += 1
                self.pos += 1
            elif c == ")":
                self.depth -= 1
                self.pos += 1
            elif c.isalpha() or c == "_":
                self._read_word()
            else:
                self.pos += 1

    def _client_line(self):
        """At the start of a line: a GO (SQL Server) or DELIMITER (MySQL) line is the client's, not SQL"""
        if self.db_type == "SQLSERVER":
            match = _GO_LINE.match(self.sql, self.pos)
            if match:
                self.go_lines.append((self.pos, match.end()))
                self.pos = match.end()
                return True
        elif self.mysql:
            match = _DELIMITER_LINE.match(self.sql, self.pos)
            if match:
                self.cuts.append((self.pos, match.end()))
                self.delimiter = match.group(1)
                self.pos = match.end()
                return True
        return False

    def _read_word(self):
        start = self.pos
        while self.pos < len(self.sql) and (self.sql[self.pos].isalnum() or self.sql[self.pos] in "_$"):
            if self.pos > start and self.sql.startswith(self.delimiter, self.pos):
                break  # END$$ under DELIMITER $$: the word ends where the delimiter starts
            self.pos += 1
        word = self.sql[start:self.pos]
        # PostgreSQL E'...' strings honour backslash escapes; plain ones do not
        if self.db_type == "POSTGRESQL" and word in ("E", "e") and self.peek() == "'":
            self._skip_quoted("'", backslashes=True)
            return
        self.words.append((word.upper(), self.depth))

    def _starts_line_comment(self):
        c = self.peek()
        if c == "-" and self.peek(1) == "-":
            # MySQL only starts a comment at "-- ": "1--1" is arithmetic there
            after = self.peek(2)
            return not self.mysql or after == "" or after.isspace()
        return c == "#" and self.mysql

    def _skip_block_comment(self):
        # PostgreSQL and SQL Server nest block comments; MySQL ends at the first */
        nests = not self.mysql
        level, i = 0, self.pos
        while i < len(self.sql):
            if self.sql.startswith("/*", i):
                level = level + 1 if (nests or level == 0) else level
                i += 2
            elif self.sql.startswith("*/", i):
                level -= 1
                i += 2
                if level == 0:
                    break
            else:
                i += 1
        self.pos = i

    def _skip_quoted(self, close, backslashes=False):
        i = self.pos + 1
        while i < len(self.sql):
            c = self.sql[i]
            if backslashes and c == "\\":
                i += 2
                continue
            if c == close:
                if self.sql[i + 1:i + 2] == close:  # doubled: an escaped quote
                    i += 2
                    continue
                break
            i += 1
        self.pos = i + 1  # an unterminated quote runs to the end: the database will say so

    def _skip_dollar_quoted(self):
        i = self.pos + 1
        while i < len(self.sql) and (self.sql[i].isalnum() or self.sql[i] == "_"):
            i += 1
        if i >= len(self.sql) or self.sql[i] != "$" or self.sql[self.pos + 1:self.pos + 2].isdigit():
            self.pos += 1  # a lone $ or a $1 parameter
            return
        tag = self.sql[self.pos:i + 1]
        close = self.sql.find(tag, i + 1)
        self.pos = len(self.sql) if close < 0 else close + len(tag)
