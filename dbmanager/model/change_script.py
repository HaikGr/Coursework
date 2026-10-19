"""Turning every edit made for one database into one script, in an order the database accepts."""

from dbmanager.sql import generator as sqlgen


def build_change_script(tables, links, db_links, db_type):
    """The SQL that saves every edit made for one database.

    tables:   {table name: TableState}
    links:    PK-FK links drawn on the diagram, as (pk_table, pk_field, fk_table, fk_field)
    db_links: the links the database already has as foreign keys

    Order: dropped tables (children first), column changes, new tables (referenced ones first),
    new foreign keys, then row changes (parents before children).
    """
    links = [link for link in links if link[0] in tables and link[2] in tables]
    # Order by the database's own foreign keys too: a table marked for dropping has left the diagram
    # together with its links, but its child must still be dropped first
    known = links + [link for link in sorted(db_links, key=lambda link: tuple(map(str, link)))
                     if link[0] in tables and link[2] in tables and link not in links]
    order = parents_first(list(tables), known)

    schema, foreign_keys, data = [], [], []
    for name in reversed(order):
        if tables[name].live and tables[name].pending_drop:
            schema.extend(tables[name].schema_statements([]))
    for name in order:
        table = tables[name]
        if table.live and not table.pending_drop:
            schema.extend(table.schema_statements([]))
    for name in order:
        table = tables[name]
        if not table.live:
            references = [(fk_field, pk_table, pk_field)
                          for pk_table, pk_field, fk_table, fk_field in links
                          if fk_table == name and not tables[pk_table].pending_drop]
            schema.extend(table.schema_statements(references))
    for link in links:
        pk_table, pk_field, fk_table, fk_field = link
        child, parent = tables[fk_table], tables[pk_table]
        if (child.live and not child.view and not child.pending_drop and not parent.pending_drop
                and link not in db_links):
            foreign_keys.append(sqlgen.add_foreign_key(fk_table, fk_field, pk_table, pk_field, db_type))
    for name in order:
        data.extend(tables[name].data_statements())
    return schema + foreign_keys + data


def parents_first(names, links):
    """Order tables so a referenced table comes before the tables pointing at it (cycles keep their order)."""
    parents = {name: [pk for pk, _, fk, _ in links if fk == name and pk != name] for name in names}
    ordered, done, visiting = [], set(), set()

    def visit(name):
        if name in done or name in visiting:
            return
        visiting.add(name)
        for parent in parents[name]:
            visit(parent)
        visiting.discard(name)
        done.add(name)
        ordered.append(name)

    for name in names:
        visit(name)
    return ordered
