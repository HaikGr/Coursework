"""The catalogues: every language says everything English says, with the same placeholders, and every key the
code names exists. No Qt."""

import os
import re
import string
import unittest
from pathlib import Path
from unittest import mock

from dbmanager import i18n
from dbmanager.i18n import LANGUAGES, catalogue, is_plural, plural_form, tr, trn

SOURCE_DIR = Path(i18n.__file__).resolve().parent.parent
NAMESPACES = sorted(path.stem for path in (i18n.LOCALES_DIR / i18n.DEFAULT_LANGUAGE).glob("*.json"))
# A key written out in the code: "<namespace>.<path>" (one ending in "." is a prefix completed at run time)
KEY_IN_SOURCE = re.compile(r"""["']((?:%s)\.[a-z0-9_.]*[a-z0-9_])["']""" % "|".join(NAMESPACES))
# The plural forms each language needs (CLDR, whole numbers)
REQUIRED_FORMS = {"en": {"one", "other"}, "ru": {"one", "few", "many"}, "hy": {"one", "other"}}


def placeholders(value):
    texts = value.values() if isinstance(value, dict) else [value]
    return {field for text in texts for _, field, _, _ in string.Formatter().parse(text) if field}


class CatalogueTest(unittest.TestCase):
    def test_every_language_has_exactly_the_keys_of_english(self):
        english = set(catalogue("en"))
        for language in LANGUAGES:
            keys = set(catalogue(language.code))
            self.assertEqual(sorted(english - keys), [], f"{language.code} lacks these")
            self.assertEqual(sorted(keys - english), [], f"{language.code} has these English does not")

    def test_a_translation_fills_the_same_placeholders_as_english(self):
        for language in LANGUAGES:
            for key, english in catalogue("en").items():
                translated = catalogue(language.code)[key]
                self.assertEqual(is_plural(translated), is_plural(english), f"{language.code} {key}: plural or not")
                expected = placeholders(english) - ({"count"} if is_plural(english) else set())
                found = placeholders(translated) - ({"count"} if is_plural(english) else set())
                self.assertEqual(found, expected, f"{language.code} {key}")

    def test_plural_texts_have_the_forms_of_their_language(self):
        for language in LANGUAGES:
            for key, value in catalogue(language.code).items():
                if is_plural(value):
                    missing = REQUIRED_FORMS[language.code] - set(value)
                    self.assertFalse(missing, f"{language.code} {key} lacks the forms {sorted(missing)}")

    def test_no_text_is_left_empty_or_untranslated_by_accident(self):
        for language in LANGUAGES:
            for key, value in catalogue(language.code).items():
                for text in (value.values() if isinstance(value, dict) else [value]):
                    self.assertTrue(text.strip(), f"{language.code} {key} is empty")

    def test_every_key_the_code_names_exists(self):
        english = catalogue("en")
        missing = []
        for path in sorted(SOURCE_DIR.rglob("*.py")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for key in KEY_IN_SOURCE.findall(line):
                    if key not in english and not any(other.startswith(key + ".") for other in english):
                        missing.append(f"{path.relative_to(SOURCE_DIR)}:{line_number} {key}")
        self.assertEqual(missing, [])


class TranslateTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_plural_forms(self):
        self.assertEqual([plural_form("en", n) for n in (0, 1, 2, 5)], ["other", "one", "other", "other"])
        self.assertEqual([plural_form("ru", n) for n in (1, 2, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111)],
                         ["one", "few", "few", "many", "many", "many", "many", "one", "few", "many", "one", "many"])
        self.assertEqual([plural_form("hy", n) for n in (0, 1, 2, 5)], ["one", "one", "other", "other"])

    def test_texts_follow_the_language(self):
        i18n.set_language("ru")
        self.assertEqual(tr("common.cancel"), "Отмена")
        i18n.set_language("hy")
        self.assertEqual(tr("common.cancel"), "Չեղարկել")
        i18n.set_language("xx")  # not supported: the default
        self.assertEqual(i18n.language().code, "en")
        self.assertEqual(tr("dashboard.top_bar.account", username="ann"), "Connected User: ann  ▾")

    def test_a_language_is_matched_from_a_locale_name(self):
        self.assertEqual([i18n.match_language(name) for name in ("ru_RU", "hy-AM", "en_US.UTF-8", "de_DE", "", None)],
                         ["ru", "hy", "en", None, None, None])

    def test_a_missing_translation_falls_back_to_english_outside_the_tests(self):
        i18n.set_language("ru")
        with mock.patch.dict(os.environ, {"DB_MANAGER_STRICT_I18N": "0"}), \
                mock.patch.dict(catalogue("ru"), clear=False) as russian:
            del russian["common.cancel"]
            self.assertEqual(tr("common.cancel"), "Cancel")
            self.assertEqual(tr("no.such.key"), "no.such.key")
        with self.assertRaises(KeyError):
            tr("no.such.key")  # in the tests it is an error

    def test_a_list_is_joined_in_the_language(self):
        self.assertEqual(i18n.join_list(["a", "b", "c"]), "a, b and c")
        i18n.set_language("ru")
        self.assertEqual(i18n.join_list(["a", "b"]), "a и b")
        self.assertEqual(i18n.join_list(["a"]), "a")

    def test_trn_picks_the_form(self):
        i18n.set_language("ru")
        with mock.patch.dict(catalogue("ru"), {"x.rows": {"one": "{count} строка", "few": "{count} строки",
                                                          "many": "{count} строк"}}):
            self.assertEqual([trn("x.rows", n) for n in (1, 3, 5, 21)],
                             ["1 строка", "3 строки", "5 строк", "21 строка"])


if __name__ == "__main__":
    unittest.main()
