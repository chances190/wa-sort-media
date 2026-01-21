"""
Simple SQLite schema mapper.

Usage:
  python sqlite_schema_map.py path/to/db.sqlite [--include-views]
"""
import argparse
import sqlite3
import sys
from typing import TypedDict, Any


# TypedDicts to make the schema shape explicit to type-checkers
class ColumnInfo(TypedDict):
    # previously some keys like 'name' and 'pk' were optional; make them required
    cid: int
    name: str
    # sqlite may return None for type in some cases so make it optional
    type: str | None
    # change to bool to match runtime values
    notnull: bool
    dflt_value: Any | None
    pk: int


class ForeignKeyCol(TypedDict):
    # match runtime usage: 'from_' / 'to' / 'seq' are expected
    from_: str
    to: str
    seq: int


class ForeignKeyInfo(TypedDict):
    # ensure 'columns' is required since the code appends to it
    id: int
    # keep seq required since we now set it on creation
    seq: int
    table: str
    columns: list[ForeignKeyCol]
    on_update: str | None
    on_delete: str | None
    match: str | None


class IndexInfo(TypedDict):
    name: str
    # use bools for runtime values
    unique: bool
    origin: str
    partial: bool
    # include columns list (was missing)
    columns: list[str]


class TableMeta(TypedDict, total=False):
    type: str
    columns: list[ColumnInfo]
    pk: list[str]
    foreign_keys: list[ForeignKeyInfo]
    indexes: list[IndexInfo]


SchemaType = dict[str, TableMeta]


def _sq(s: str) -> str:
    # escape single quotes for PRAGMA usage
    return s.replace("'", "''")


def list_tables(conn: sqlite3.Connection, include_views: bool = False) -> list[tuple[str, str]]:
    q = ("SELECT name, type FROM sqlite_master "
         "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
         if include_views else
         "SELECT name, type FROM sqlite_master "
         "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    rows = conn.execute(q).fetchall()
    # Normalize values to (name, type) as strings
    return [(str(r[0]), str(r[1])) for r in rows]


def map_schema(conn: sqlite3.Connection, include_views: bool = False) -> SchemaType:
    conn.execute("PRAGMA foreign_keys = ON;")
    schema: SchemaType = {}
    for name, typ in list_tables(conn, include_views):
        table_meta: TableMeta = {"type": typ}
        # columns
        cols: list[ColumnInfo] = []
        for r in conn.execute(f"PRAGMA table_info('{_sq(name)}')"):
            # r: cid, name, type, notnull, dflt_value, pk
            cid = int(r[0])
            col_name = str(r[1])
            # preserve unknown/empty types as None so we don't render the string 'None'
            col_type = r[2] if r[2] is not None and str(r[2]) != "" else None
            # store as bool to match ColumnInfo.notnull
            notnull = bool(r[3])
            default = r[4]
            pk = int(r[5])
            cols.append({
                "cid": cid,
                "name": col_name,
                "type": col_type,
                "notnull": notnull,
                # use dflt_value (matches TypedDict and PRAGMA column name)
                "dflt_value": default,
                "pk": pk
            })
        table_meta["columns"] = cols
        # primary key (ordered)
        pk = [c["name"] for c in sorted([c for c in cols if c["pk"]], key=lambda x: x["pk"])]
        if pk:
            table_meta["pk"] = pk
        # foreign keys (group by id -> supports composite fks)
        fk_rows = conn.execute(f"PRAGMA foreign_key_list('{_sq(name)}')").fetchall()
        fks: dict[int, ForeignKeyInfo] = {}
        for r in fk_rows:
            # r: id, seq, table, from, to, on_update, on_delete, match
            fid = int(r[0])
            seq = int(r[1])
            ref_table = str(r[2])
            col_from = str(r[3])
            col_to = str(r[4]) if r[4] is not None else ""
            on_update = str(r[5]) if r[5] is not None else ""
            on_delete = str(r[6]) if r[6] is not None else ""
            match = str(r[7]) if r[7] is not None else ""
            if fid not in fks:
                # include seq so the dict matches ForeignKeyInfo
                fks[fid] = {
                    "id": fid,
                    "seq": seq,
                    "table": ref_table,
                    "on_update": on_update,
                    "on_delete": on_delete,
                    "match": match,
                    "columns": []
                }
            fks[fid]["columns"].append({"from_": col_from, "to": col_to, "seq": seq})
        table_meta["foreign_keys"] = list(fks.values())
        # indexes
        idxs: list[IndexInfo] = []
        for r in conn.execute(f"PRAGMA index_list('{_sq(name)}')"):
            # r: seq, name, unique, origin, partial
            idx_name = str(r[1])
            unique = bool(r[2])
            origin = str(r[3]) if len(r) > 3 and r[3] is not None else ""
            partial = bool(r[4]) if len(r) > 4 else False
            # PRAGMA index_info can return NULL for expression-based index parts; skip those
            cols_in_idx: list[str] = [str(c[2]) for c in conn.execute(f"PRAGMA index_info('{_sq(idx_name)}')") if c[2] is not None]
            # now matches IndexInfo (includes 'columns')
            idxs.append({
                "name": idx_name,
                "unique": unique,
                "origin": origin,
                "partial": partial,
                "columns": cols_in_idx
            })
        table_meta["indexes"] = idxs
        schema[name] = table_meta
    # Infer likely foreign key relationships when explicit foreign keys are not declared.
    # Heuristic: columns named '<prefix>_row_id' probably reference a table named '<prefix>'
    # or a table that has a primary key named the same column.
    next_inferred_id = -1
    # precompute pk and column maps
    table_pks: dict[str, list[str]] = {tn: inf.get("pk", []) or [] for tn, inf in schema.items()}

    for src_table, inf in list(schema.items()):
        existing_fks = inf.get("foreign_keys", []) or []
        for col in (inf.get("columns", []) or []):
            cname = col.get("name", "")
            if not cname or not cname.endswith("_row_id"):
                continue
            # find candidate target table
            prefix = cname[:-7]
            candidate = None
            # exact table name match
            if prefix in schema:
                candidate = prefix
            # any table with a pk column equal to this column name
            if candidate is None:
                for tn, pk in table_pks.items():
                    if cname in pk:
                        candidate = tn
                        break
            # table with single 'row_id' pk and name matches prefix
            if candidate is None:
                for tn, pk in table_pks.items():
                    if pk == ["row_id"] and tn == prefix:
                        candidate = tn
                        break
            # do not infer relationships to the same table (likely a PK or identity column)
            if candidate == src_table:
                continue

            # if we still don't have a candidate, skip inference
            if not candidate:
                continue

            # avoid duplicating existing declared FK to same table/column
            already = False
            for fk in existing_fks:
                for fc in fk.get("columns", []):
                    if fc.get("from_") == cname and fk.get("table") == candidate:
                        already = True
                        break
                if already:
                    break
            if already:
                continue

            # determine target column name: prefer exact matching PK column or common PK names
            target_pk = ""
            pk_list = table_pks.get(candidate, []) or []
            if pk_list:
                # prefer pk column that matches the column name
                for p in pk_list:
                    if p == cname:
                        target_pk = p
                        break
                if not target_pk:
                    # prefer columns that look like ids
                    for p in pk_list:
                        if p in ("_id", "row_id") or p.endswith("_id"):
                            target_pk = p
                            break
                if not target_pk:
                    target_pk = pk_list[0]
            else:
                # no pk information -> skip inference (avoid None/empty targets)
                continue
            fk_info: ForeignKeyInfo = {
                "id": next_inferred_id,
                "seq": 0,
                "table": candidate,
                "on_update": None,
                "on_delete": None,
                "match": None,
                "columns": [{"from_": cname, "to": target_pk, "seq": 0}]
            }
            next_inferred_id -= 1
            existing_fks.append(fk_info)
        if existing_fks:
            schema[src_table]["foreign_keys"] = existing_fks

    return schema


def print_text(schema: SchemaType) -> None:
    for tname, info in schema.items():
        print(f"{tname} ({info.get('type','table')})")
        cols_raw = info.get("columns", [])
        cols: list[ColumnInfo] = list(cols_raw)
        for c in cols:
            # explicit keyed access to satisfy type-checkers
            name = str(c.get("name", "")) if "name" in c else ""
            # avoid printing the literal 'None' when type is missing
            ctype = c.get("type") or ""
            pk = " PK" if ("pk" in c and bool(c["pk"])) else ""
            nn = " NOT NULL" if ("notnull" in c and bool(c["notnull"])) else ""
            # use dflt_value instead of 'default'
            default = c.get("dflt_value", None)
            default_str = f" default={default}" if default is not None else ""
            print(f"  {name:<20} {ctype}{pk}{nn}{default_str}")
        fks_raw = info.get("foreign_keys", [])
        fks: list[ForeignKeyInfo] = list(fks_raw)
        for fk in fks:
            cols_list_raw = fk.get("columns", [])
            cols_list: list[ForeignKeyCol] = list(cols_list_raw)
            cols_fk = ", ".join(f"{c.get('from_','')}->{c.get('to','')}" for c in cols_list)
            print(f"  FK -> {fk.get('table','')} ({cols_fk}) on_update={fk.get('on_update')} on_delete={fk.get('on_delete')}")
        indexes_raw = info.get("indexes", [])
        indexes: list[IndexInfo] = list(indexes_raw)
        for idx in indexes:
            print(f"  IDX {idx.get('name','')} unique={idx.get('unique', False)} cols={idx.get('columns', [])}")
        print()


def schema_to_dbml(schema: SchemaType) -> str:
    """
    Convert the in-memory schema mapping into a DBML-formatted string.
    """
    lines: list[str] = []
    for tname, info in schema.items():
        is_view = info.get("type") == "view"
        header = f"Table {tname}"
        if is_view:
            header += " [note: 'view']"
        lines.append(header + " {")
        # normalize indexes and columns with typed lists
        indexes_raw = info.get("indexes", [])
        indexes: list[IndexInfo] = list(indexes_raw)
        unique_single_cols: set[str] = set()
        for idx in indexes:
            cols_raw = idx.get("columns", [])
            cols_list: list[str] = [str(x) for x in cols_raw]
            if idx.get("unique") and len(cols_list) == 1:
                unique_single_cols.add(cols_list[0])
        cols_raw = info.get("columns", [])
        cols: list[ColumnInfo] = list(cols_raw)
        for c in cols:
            attrs: list[str] = []
            if ("pk" in c) and bool(c["pk"]):
                attrs.append("pk")
            if ("notnull" in c) and bool(c["notnull"]):
                attrs.append("not null")
            cname = str(c.get("name", ""))
            if cname in unique_single_cols:
                attrs.append("unique")
            # use dflt_value instead of 'default'
            default = c.get("dflt_value", None)
            if default is not None:
                d = str(default).strip()
                if (d.startswith("'") and d.endswith("'")) or (d.startswith('"') and d.endswith('"')):
                    inner = d[1:-1].replace("'", "\\'")
                    attrs.append(f"default: '{inner}'")
                else:
                    attrs.append(f"default: {d}")
            attr_str = f" [{', '.join(attrs)}]" if attrs else ""
            col_name = cname
            # omit the type if it's unknown/None to avoid 'None' literal in DBML
            col_type = str(c.get("type")) if c.get("type") else ""
            type_part = f" {col_type}" if col_type else ""
            lines.append(f"  {col_name}{type_part}{attr_str}".rstrip())
        # multi-column indexes
        multi_idx: list[str] = []
        for idx in indexes:
            cols_raw = idx.get("columns", [])
            cols_list: list[str] = [str(x) for x in cols_raw]
            if len(cols_list) > 1:
                col_list = ", ".join(cols_list)
                multi_idx.append(f"({col_list})" + (" [unique]" if idx.get("unique") else ""))
        if multi_idx:
            lines.append("")
            lines.append("  Indexes {")
            for mi in multi_idx:
                lines.append(f"    {mi}")
            lines.append("  }")
        lines.append("")
        lines.append("}")
        lines.append("")
    # foreign key refs
    # Build per-table unique column/index info to infer relation cardinality.
    table_unique_singles: dict[str, set[str]] = {}
    table_unique_multi: dict[str, set[tuple[str, ...]]] = {}
    for tn, inf in schema.items():
        us: set[str] = set()
        um: set[tuple[str, ...]] = set()
        for idx in inf.get("indexes", []):
            if idx.get("unique"):
                cols_idx = [str(x) for x in idx.get("columns", [])]
                if len(cols_idx) == 1:
                    us.add(cols_idx[0])
                elif len(cols_idx) > 1:
                    um.add(tuple(cols_idx))
        pk = inf.get("pk", []) or []
        if pk:
            if len(pk) == 1:
                us.add(pk[0])
            else:
                um.add(tuple(pk))
        table_unique_singles[tn] = us
        table_unique_multi[tn] = um

    for tname, info in schema.items():
        fks_raw = info.get("foreign_keys", [])
        fks: list[ForeignKeyInfo] = list(fks_raw)
        for fk in fks:
            fk_cols_raw = fk.get("columns", [])
            fk_cols: list[ForeignKeyCol] = list(fk_cols_raw)
            cols_sorted = sorted(fk_cols, key=lambda x: int(x.get("seq", 0)))
            # determine left/right column lists for cardinality checks
            left_cols = [str(c.get("from_","")) for c in cols_sorted]
            right_cols = [str(c.get("to","")) for c in cols_sorted]

            def is_unique(table: str, cols: list[str]) -> bool:
                if not cols:
                    return False
                us = table_unique_singles.get(table, set())
                um = table_unique_multi.get(table, set())
                if len(cols) == 1:
                    return cols[0] in us
                return tuple(cols) in um

            left_unique = is_unique(tname, left_cols)
            right_unique = is_unique(fk.get("table", ""), right_cols)
            if len(cols_sorted) == 1:
                c = cols_sorted[0]
                ref = f"Ref: {tname}.{c.get('from_','')} > {fk.get('table','')}.{c.get('to','')}"
            else:
                left = ", ".join(str(c.get('from_','')) for c in cols_sorted)
                right = ", ".join(str(c.get('to','')) for c in cols_sorted)
                ref = f"Ref: {tname} ({left}) > {fk.get('table','')} ({right})"
            extras: list[str] = []
            # include inferred cardinality: child->parent (1 or n)
            cardinality = f"{'1' if left_unique else 'n'}->{'1' if right_unique else 'n'}"
            extras.append(f"cardinality: {cardinality}")
            if fk.get("on_update"):
                extras.append(f"on_update: {fk.get('on_update')}")
            if fk.get("on_delete"):
                extras.append(f"on_delete: {fk.get('on_delete')}")
            if extras:
                ref += " /* " + ", ".join(extras) + " */"
            lines.append(ref)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Map SQLite schema to DBML/text.")
    parser.add_argument("db", help="SQLite DB file path")
    parser.add_argument("--include-views", action="store_true", help="Include views in the mapping")
    parser.add_argument("--dbml", "-b", help="Write schema DBML to file (use '-' for stdout). If omitted, DBML is printed to stdout by default.")
    parser.add_argument("--text", "-t", action="store_true", help="Print plain text instead of DBML (DBML is the default).")
    args = parser.parse_args(argv)

    try:
        conn = sqlite3.connect(args.db)
    except sqlite3.Error as e:
        print(f"Cannot open database: {e}", file=sys.stderr)
        return 2

    schema = map_schema(conn, include_views=args.include_views)
    conn.close()

    # DBML is the default. If --text is passed, emit plain text.
    if args.text:
        print_text(schema)
    else:
        dbml = schema_to_dbml(schema)
        if args.dbml:
            if args.dbml == "-":
                print(dbml)
            else:
                with open(args.dbml, "w", encoding="utf-8") as f:
                    f.write(dbml)
        else:
            # default: print DBML to stdout
            print(dbml)
    return 0


if __name__ == "__main__":
    sys.exit(main())