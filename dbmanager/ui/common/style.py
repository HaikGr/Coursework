"""Style pieces shared by several screens."""

from PyQt6.QtGui import QKeySequence

from dbmanager.config import RESOURCES_DIR

# Style sheets want forward slashes, also on Windows
_CHEVRON = (RESOURCES_DIR / "chevron_down.svg").as_posix()
# The arrow of a styled QComboBox: once a style sheet gives the box a border, Qt stops drawing its own
COMBO_ARROW = f"""
    QComboBox::drop-down {{ border: none; width: 28px; subcontrol-origin: padding; subcontrol-position: center right; }}
    QComboBox::down-arrow {{ image: url("{_CHEVRON}"); width: 12px; height: 12px; margin-right: 10px; }}
"""

# The first font of the list that is installed wins: Windows, macOS, then the usual Linux ones
MONOSPACE = "'Cascadia Mono', Consolas, 'SF Mono', Menlo, 'DejaVu Sans Mono', 'Liberation Mono', monospace"

# Context menus (the sidebar, the fields on the diagram): a theme.qss template
MENU_STYLE = """
    QMenu { background-color: @surface; color: @text; border: 1px solid @border_strong; padding: 4px; font-size: 13px; }
    QMenu::item { padding: 6px 18px; border-radius: 4px; }
    QMenu::item:selected { background-color: @accent; color: @on_accent; }
    QMenu::item:disabled { color: @text_disabled; }
    QMenu::separator { height: 1px; background: @border; margin: 4px 6px; }
    QMenu::indicator { width: 14px; height: 14px; }
"""


def shortcut_text(keys):
    """'Ctrl+Return' as the user reads it: Ctrl+Enter, or ⌘↩ on a Mac"""
    return QKeySequence(keys).toString(QKeySequence.SequenceFormat.NativeText).replace("Return", "Enter")
