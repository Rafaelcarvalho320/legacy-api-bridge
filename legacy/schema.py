"""Creating the legacy tables from the SQL a DBA would recognise.

Django owns none of these tables, so there is no migration for them. The suite
and the demo both build them by running the same ``.sql`` files, which keeps
one description of the legacy schema instead of two that drift apart.
"""

from __future__ import annotations

from pathlib import Path

from django.db import connection

SQL_DIR = Path(__file__).resolve().parent / "sql"
SCHEMA_FILE = SQL_DIR / "legacy_schema.sql"
SEED_FILE = SQL_DIR / "legacy_seed.sql"

#: Quoted, and in dependency order. PostgreSQL folds an unquoted
#: identifier to lower case, so CREATE TABLE TB_CLI makes a table called
#: tb_cli while Django emits FROM "TB_CLI" - and the two never meet.
TABLES = ('"TB_PEDITE"', '"TB_PED"', '"TB_CLI"', '"TB_CID"')


def statements(path: Path) -> list[str]:
    """Split a script into statements, dropping comments and blank lines.

    Deliberately naive: these files contain no procedures, no triggers and no
    semicolons inside string literals. A real SQL splitter would be a
    dependency bought to solve a problem this project does not have.
    """
    text = "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )
    return [chunk.strip() for chunk in text.split(";") if chunk.strip()]


def create_schema() -> None:
    with connection.cursor() as cursor:
        for statement in statements(SCHEMA_FILE):
            cursor.execute(statement)


def load_seed() -> None:
    with connection.cursor() as cursor:
        for statement in statements(SEED_FILE):
            cursor.execute(statement)


def drop_schema() -> None:
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")


def reset(seed: bool = True) -> None:
    drop_schema()
    create_schema()
    if seed:
        load_seed()
