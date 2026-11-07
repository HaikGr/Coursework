"""The light and the dark theme: every colour the app shows is one of these tokens.

Style sheets name tokens instead of colours - "QLabel { color: @text_muted; }" - and qss() fills them in
from the current theme. style(widget, template) sets a widget's sheet now and again whenever the theme
changes; painting code asks color("token") each time it paints. A token that does not exist raises, so a
typo cannot slip through as a black or transparent area.

Both themes keep body text at 4.5:1 or more against the surfaces it sits on (WCAG AA); a token named
on_<x> is the text colour that reads on <x>.
"""

import re
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

from dbmanager.ui.common.live import bind


@dataclass(frozen=True)
class Theme:
    name: str            # "light" or "dark", as stored in the preferences
    scheme: Qt.ColorScheme
    colors: dict


# Surfaces, from the back: window (behind the panels) and canvas (the diagram), then surface (panels,
# cards, the sidebar, dialogs and menus), surface_alt (bands inside a surface: toolbars, card headers and
# footers, table headers), surface_raised (neutral buttons, badges, chips) and sunken (inputs, editors).
LIGHT = Theme("light", Qt.ColorScheme.Light, {
    "window": "#F1F5F9",
    "canvas": "#E8EDF4",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "surface_raised": "#E2E8F0",
    "surface_hover": "#EEF2F7",
    "surface_pressed": "#CBD5E1",
    "sunken": "#FFFFFF",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "grid_line": "#E2E8F0",
    "row_alt": "#F8FAFC",

    "text": "#1E293B",
    "text_secondary": "#475569",
    "text_muted": "#556479",
    "text_disabled": "#94A3B8",
    "placeholder": "#94A3B8",

    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_pressed": "#1E40AF",
    "accent_subtle": "#DBEAFE",
    "accent_text": "#1D4ED8",
    "on_accent": "#FFFFFF",
    "focus": "#3B82F6",
    "selection": "#2563EB",
    "on_selection": "#FFFFFF",

    "info": "#0284C7",
    "info_hover": "#0369A1",
    "info_subtle": "#E0F2FE",
    "info_text": "#0369A1",
    "on_info": "#FFFFFF",

    "success": "#15803D",
    "success_hover": "#166534",
    "success_subtle": "#DCFCE7",
    "success_text": "#15803D",
    "on_success": "#FFFFFF",

    "warning": "#F59E0B",
    "warning_hover": "#D97706",
    "warning_subtle": "#FEF3C7",
    "warning_text": "#B45309",
    "on_warning": "#422006",

    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_subtle": "#FEE2E2",
    "danger_text": "#B91C1C",
    "on_danger": "#FFFFFF",

    # Toggles that change the query's options (Distinct, Count rows) once switched on
    "option": "#0F766E",
    "option_hover": "#115E59",
    "on_option": "#FFFFFF",

    "purple": "#7C3AED",
    "purple_subtle": "#EDE9FE",
    "purple_text": "#6D28D9",

    # The amber bands that head the sidebar and the schema
    "highlight": "#FBC840",
    "on_highlight": "#5C3A0B",

    # The blue top bar, and what sits on it
    "brand": "#2B68E0",
    "on_brand": "#FFFFFF",
    "on_brand_muted": "#EEF4FF",
    "brand_hover": "rgba(255, 255, 255, 0.22)",
    "brand_border": "rgba(255, 255, 255, 0.6)",

    # The sign-in windows: an animated background and a card on it
    "auth_background": "#2B68E0",
    "auth_card": "#DCE7FA",
    "auth_input": "#FFFFFF",
    "auth_input_text": "#334155",
    "auth_heading": "#334155",
    "auth_text": "#475569",

    "scrollbar": "#CBD5E1",
    "scrollbar_hover": "#94A3B8",
    "shadow": "rgba(15, 23, 42, 0.18)",
    "tooltip": "#1E293B",
    "on_tooltip": "#F8FAFC",
    "null_text": "#94A3B8",

    # Key badges and the lines of the diagram
    "pk": "#FDE68A",
    "on_pk": "#713F12",
    "fk": "#BFDBFE",
    "on_fk": "#1E3A8A",
    "link": "#2563EB",
    "link_join": "#0D9488",
    "link_draft": "#D97706",
    "link_ok": "#16A34A",

    # SQL: the editor and its highlighting
    "code_background": "#F8FAFC",
    "code_text": "#1E293B",
    "code_keyword": "#7C3AED",
    "code_table": "#1D4ED8",
    "code_field": "#047857",
    "code_number": "#C2410C",
    "code_string": "#A16207",
    "code_operator": "#BE123C",
})

DARK = Theme("dark", Qt.ColorScheme.Dark, {
    "window": "#0F172A",
    "canvas": "#0B1120",
    "surface": "#1E293B",
    "surface_alt": "#182234",
    "surface_raised": "#334155",
    "surface_hover": "#273449",
    "surface_pressed": "#41506A",
    "sunken": "#0F172A",
    "border": "#334155",
    "border_strong": "#475569",
    "grid_line": "#2B3A52",
    "row_alt": "#223047",

    "text": "#E2E8F0",
    "text_secondary": "#CBD5E1",
    "text_muted": "#A3B1C6",
    "text_disabled": "#64748B",
    "placeholder": "#64748B",

    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_pressed": "#1E40AF",
    "accent_subtle": "#1E3A5F",
    "accent_text": "#60A5FA",
    "on_accent": "#FFFFFF",
    "focus": "#3B82F6",
    "selection": "#2563EB",
    "on_selection": "#FFFFFF",

    "info": "#0284C7",
    "info_hover": "#0369A1",
    "info_subtle": "#0C3A57",
    "info_text": "#7DD3FC",
    "on_info": "#FFFFFF",

    "success": "#15803D",
    "success_hover": "#166534",
    "success_subtle": "#163D2A",
    "success_text": "#86EFAC",
    "on_success": "#FFFFFF",

    "warning": "#F59E0B",
    "warning_hover": "#FBBF24",
    "warning_subtle": "#422006",
    "warning_text": "#FBBF24",
    "on_warning": "#1C1917",

    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_subtle": "#4C1414",
    "danger_text": "#FCA5A5",
    "on_danger": "#FFFFFF",

    "option": "#0F766E",
    "option_hover": "#115E59",
    "on_option": "#FFFFFF",

    "purple": "#7C3AED",
    "purple_subtle": "#2E1A5E",
    "purple_text": "#C4B5FD",

    "highlight": "#3D2C0E",
    "on_highlight": "#FCD34D",

    "brand": "#1E3A8A",
    "on_brand": "#FFFFFF",
    "on_brand_muted": "#D6E0F5",
    "brand_hover": "rgba(255, 255, 255, 0.16)",
    "brand_border": "rgba(255, 255, 255, 0.45)",

    "auth_background": "#13254F",
    "auth_card": "#1E293B",
    "auth_input": "#0F172A",
    "auth_input_text": "#E2E8F0",
    "auth_heading": "#F1F5F9",
    "auth_text": "#A7B4C8",

    "scrollbar": "#475569",
    "scrollbar_hover": "#64748B",
    "shadow": "rgba(0, 0, 0, 0.55)",
    "tooltip": "#334155",
    "on_tooltip": "#F8FAFC",
    "null_text": "#64748B",

    "pk": "#F6C344",
    "on_pk": "#1A202C",
    "fk": "#60A5FA",
    "on_fk": "#0F172A",
    "link": "#69A7FF",
    "link_join": "#2DD4BF",
    "link_draft": "#FFD57F",
    "link_ok": "#4ADE80",

    "code_background": "#0F172A",
    "code_text": "#E2E8F0",
    "code_keyword": "#C792EA",
    "code_table": "#82AAFF",
    "code_field": "#C3E88D",
    "code_number": "#F78C6C",
    "code_string": "#FFCB6B",
    "code_operator": "#FF5370",
})

THEMES = (LIGHT, DARK)
_BY_NAME = {theme.name: theme for theme in THEMES}
_current = LIGHT

_TOKEN = re.compile(r"@([a-z][a-z0-9_]*)")
_RGBA = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)")


def current():
    return _current


def set_theme(name):
    """Make the named theme current (an unknown name means light). Preferences applies it to the app."""
    global _current
    _current = _BY_NAME.get(name, LIGHT)


def theme_named(name):
    return _BY_NAME.get(name)


def value(token):
    """A token's colour as written in a style sheet ("#2563EB" or "rgba(...)")."""
    try:
        return _current.colors[token]
    except KeyError:
        raise KeyError(f"The theme has no colour called '{token}'") from None


def qss(template):
    """A style sheet with every @token replaced by the current theme's colour."""
    return _TOKEN.sub(lambda match: value(match.group(1)), template)


def color(token, alpha=None):
    """A token as a QColor, for painting; alpha (0-255) overrides its opacity."""
    text = value(token)
    match = _RGBA.fullmatch(text)
    if match:
        red, green, blue, opacity = match.groups()
        result = QColor(int(red), int(green), int(blue), round(float(opacity) * 255))
    else:
        result = QColor(text)
    if alpha is not None:
        result.setAlpha(alpha)
    return result


def style(widget, template):
    """Give a widget the style sheet of a template now, and again whenever the theme changes. Calling it
    again replaces the template (for a widget whose look follows its state)."""
    bind(widget.setStyleSheet, lambda: qss(template))


def palette():
    """The Fusion palette of the current theme: what style sheets leave to the style (tooltips, the menus of
    text fields, check marks) follows the theme too."""
    result = QPalette()
    roles = QPalette.ColorRole
    for role, token in (
            (roles.Window, "surface"), (roles.WindowText, "text"), (roles.Base, "sunken"),
            (roles.AlternateBase, "row_alt"), (roles.Text, "text"), (roles.PlaceholderText, "placeholder"),
            (roles.Button, "surface_raised"), (roles.ButtonText, "text"), (roles.BrightText, "on_danger"),
            (roles.Highlight, "selection"), (roles.HighlightedText, "on_selection"),
            (roles.ToolTipBase, "tooltip"), (roles.ToolTipText, "on_tooltip"),
            (roles.Link, "accent_text"), (roles.LinkVisited, "purple_text"),
            (roles.Light, "surface_alt"), (roles.Midlight, "border"), (roles.Mid, "border_strong"),
            (roles.Dark, "scrollbar_hover"), (roles.Shadow, "shadow")):
        result.setColor(role, color(token))
    disabled = QPalette.ColorGroup.Disabled
    for role in (roles.WindowText, roles.Text, roles.ButtonText):
        result.setColor(disabled, role, color("text_disabled"))
    return result
