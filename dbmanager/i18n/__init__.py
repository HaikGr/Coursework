"""Translations: every text the user reads comes from here (no Qt, so db/ and model/ use it too).

The catalogues are locales/<language>/<area>.json. A key is the file's name followed by the path inside
it: "auth.sign_in.heading" is {"sign_in": {"heading": ...}} in auth.json. A value is a str.format
template ("Connected User: {username}"), or, for a text that depends on a number, an object of CLDR plural
forms read with trn(): {"one": "{count} row", "other": "{count} rows"} - Russian also has "few" and "many".

English is the reference. A key another language lacks falls back to English and is logged once; a key
English lacks is a bug, and with DB_MANAGER_STRICT_I18N=1 (the tests set it) both raise KeyError. The
tests also check that every language has the keys and placeholders of English.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@dataclass(frozen=True)
class Language:
    code: str   # the catalogue's directory
    tag: str    # BCP 47, sent to the server as Accept-Language
    name: str   # in the language itself, as the selector shows it


LANGUAGES = (
    Language("hy", "hy-AM", "Հայերեն"),
    Language("ru", "ru-RU", "Русский"),
    Language("en", "en-US", "English"),
)
DEFAULT_LANGUAGE = "en"
_BY_CODE = {language.code: language for language in LANGUAGES}

PLURAL_FORMS = frozenset({"zero", "one", "two", "few", "many", "other"})

_catalogues = {}
_current = DEFAULT_LANGUAGE
_reported = set()


def strict():
    return os.environ.get("DB_MANAGER_STRICT_I18N") == "1"


def language():
    """The Language texts are in now."""
    return _BY_CODE[_current]


def set_language(code):
    """Switch every later tr() to this language; an unknown code means the default."""
    global _current
    _current = code if code in _BY_CODE else DEFAULT_LANGUAGE


def match_language(name):
    """The supported language code of a locale name such as 'ru_RU', 'hy-AM' or 'en', else None."""
    if not name:
        return None
    code = re.split(r"[-_.@]", name.strip(), maxsplit=1)[0].lower()
    return code if code in _BY_CODE else None


def is_plural(value):
    """Plural forms rather than a group of keys: Russian needs no "other" for whole numbers"""
    return isinstance(value, dict) and bool(value) and set(value) <= PLURAL_FORMS


def catalogue(code):
    """{key: template or plural forms} of one language, every area merged."""
    if code not in _catalogues:
        merged = {}
        for path in sorted((LOCALES_DIR / code).glob("*.json")):
            _flatten(path.stem, json.loads(path.read_text(encoding="utf-8")), merged)
        _catalogues[code] = merged
    return _catalogues[code]


def _flatten(prefix, node, into):
    for name, value in node.items():
        key = f"{prefix}.{name}"
        if isinstance(value, dict) and not is_plural(value):
            _flatten(key, value, into)
        else:
            into[key] = value


def _lookup(key):
    value = catalogue(_current).get(key)
    if value is not None:
        return value
    fallback = catalogue(DEFAULT_LANGUAGE).get(key)
    if fallback is None or strict():
        if strict():
            raise KeyError(f"No translation for '{key}' in '{_current}'")
        _report(key, f"No text for '{key}' in any language")
        return key
    _report((key, _current), f"No {_current} translation for '{key}', showing English")
    return fallback


def _report(token, message):
    if token not in _reported:
        _reported.add(token)
        log.warning(message)


def _format(key, template, params):
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        if strict():
            raise
        _report((key, "format"), f"The text of '{key}' does not fit its parameters {sorted(params)}")
        return template


def tr(key, /, **params):
    """The text of key in the current language, with {name} placeholders filled from params."""
    value = _lookup(key)
    if isinstance(value, dict):
        if strict():
            raise KeyError(f"'{key}' has plural forms: read it with trn()")
        value = value["other"]
    return _format(key, value, params)


def trn(key, count, /, **params):
    """The text of key for a number: its plural form for count in the current language ({count} is filled)."""
    value = _lookup(key)
    if not isinstance(value, dict):
        if strict():
            raise KeyError(f"'{key}' has no plural forms: read it with tr()")
        return _format(key, value, {"count": count, **params})
    template = value.get(plural_form(_current, count)) or value.get("other") or next(iter(value.values()))
    return _format(key, template, {"count": count, **params})


def plural_form(code, count):
    """The CLDR plural category of a whole number in a language."""
    n = abs(int(count))
    if code == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    if code == "hy":
        return "one" if n in (0, 1) else "other"
    return "one" if n == 1 else "other"


def join_list(items):
    """'a, b and c' in the current language."""
    items = [str(item) for item in items]
    if len(items) < 2:
        return "".join(items)
    return tr("common.list_join", head=tr("common.list_separator").join(items[:-1]), last=items[-1])
