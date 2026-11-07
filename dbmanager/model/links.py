"""Linking two fields of different tables: which one is the key the other points at, and whether they can be
linked at all. A link is a foreign key in the making: the field that points (the child) refers to the primary
key of another table (the parent); queries join the two tables on it."""

from dataclasses import dataclass

from dbmanager.i18n import tr
from dbmanager.sql.generator import base_type, is_numeric_type, is_text_type


def type_family(type_name):
    """What kind of values a type holds - number, text, time, boolean, uuid - or None when it is not known.
    Two fields are compared, joined or linked only within one family."""
    base = base_type(type_name)
    if not base:
        return None
    if is_numeric_type(type_name):
        return "number"
    if is_text_type(type_name):
        return "text"
    if base in ("bit", "bool", "boolean"):
        return "boolean"
    if base in ("uuid", "uniqueidentifier"):
        return "uuid"
    if "date" in base or "time" in base:
        return "time"
    return base


def same_family(type_a, type_b):
    family_a, family_b = type_family(type_a), type_family(type_b)
    return family_a is None or family_b is None or family_a == family_b


@dataclass(frozen=True)
class End:
    """One field of a link"""
    table: str
    field: str
    type_name: str = ""
    primary: bool = False

    def __str__(self):
        return f"{self.table}.{self.field}"


def plan_link(source, target):
    """(parent, child) - the key and the field that will point at it - or a sentence saying why these two
    cannot be linked. source is where the link was started: when both are primary keys it is the parent
    (a one-to-one link)."""
    if source.table == target.table:
        return tr("model.links.same_table", source=source, target=target)
    if not source.primary and not target.primary:
        return tr("model.links.no_primary_key", source=source, target=target)
    parent, child = (source, target) if source.primary else (target, source)
    if not same_family(parent.type_name, child.type_name):
        return tr("model.links.different_kinds", parent=parent, parent_type=parent.type_name, child=child,
                  child_type=child.type_name)
    return parent, child
