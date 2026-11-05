"""Values read from a database, in the shapes the editor works with: None, bool, int, Decimal or text.

The editor compares cells as text and writes them back as SQL literals (see sql.generator.literal), so a
date or a JSON document is best kept in the database's own text form: that is what it accepts back.
Numbers stay numbers; a float becomes a Decimal, as a JSON number from the server used to."""

import functools
import json
import math
from datetime import datetime
from decimal import Decimal

MAX_TEXT_LENGTH = 10_000


def to_value(value):
    if value is None or isinstance(value, (bool, int, Decimal)):
        return value
    if isinstance(value, str):
        return value[:MAX_TEXT_LENGTH]
    if isinstance(value, float):
        return Decimal(repr(value)) if math.isfinite(value) else str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "0x" + bytes(value)[:MAX_TEXT_LENGTH // 2].hex()
    if isinstance(value, datetime):
        text = value.isoformat(sep=" ")
        if "." in text:  # 12:00:00.120000 -> 12:00:00.12: SQL Server's datetime takes at most 3 digits
            head, _, tail = text.partition(".")
            fraction, zone = tail[:6], tail[6:]
            fraction = fraction.rstrip("0")
            text = head + (f".{fraction}" if fraction else "") + zone
        return text
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def bit_to_int(value):
    """MySQL hands BIT(n) columns over as bytes."""
    return int.from_bytes(value, "big") if isinstance(value, (bytes, bytearray)) else value


@functools.cache
def postgres_text_context():
    """psycopg adapters that turn everything except numbers and booleans into PostgreSQL's own text."""
    from psycopg import postgres
    from psycopg.adapt import AdaptersMap
    from psycopg.types.string import TextLoader

    native = {"int2", "int4", "int8", "oid", "numeric", "float4", "float8", "bool"}
    adapters = AdaptersMap(postgres.adapters)
    for info in postgres.types:
        if info.name not in native:
            adapters.register_loader(info.oid, TextLoader)
        if info.array_oid:
            adapters.register_loader(info.array_oid, TextLoader)
    return adapters


@functools.cache
def mysql_conversions():
    """PyMySQL's conversions, except that dates and times stay text ('0000-00-00' included)."""
    from pymysql import converters
    from pymysql.constants import FIELD_TYPE

    as_text = {FIELD_TYPE.DATE, FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.TIME, FIELD_TYPE.NEWDATE}
    return {key: decoder for key, decoder in converters.conversions.items() if key not in as_text}
