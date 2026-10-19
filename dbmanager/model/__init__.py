"""Editor state without widgets: what changed, and the SQL that saves it."""

from dbmanager.model.change_script import build_change_script
from dbmanager.model.table_state import TableState, cell_text

__all__ = ["TableState", "build_change_script", "cell_text"]
