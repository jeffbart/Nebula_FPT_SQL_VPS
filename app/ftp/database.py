"""Acesso assíncrono ao SQL Server usando autenticação integrada do Windows."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Callable, TypeVar

import pyodbc

logger = logging.getLogger(__name__)
T = TypeVar("T")

DEFAULT_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=NebulaFTP;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)


class Database:
    """Executa operações SQL bloqueantes fora do event loop."""

    def __init__(self, connection_string: str | None = None) -> None:
        self.connection_string = (
            connection_string
            or os.environ.get("NEBULA_DB_CONNECTION")
            or DEFAULT_CONNECTION_STRING
        )

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self.connection_string, timeout=15)

    async def execute(self, sql: str, parameters: Sequence[Any] = ()) -> int:
        """Executa um comando e devolve a quantidade de linhas afetadas."""

        def operation() -> int:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(sql, parameters)
                rowcount = cursor.rowcount
                connection.commit()
                return rowcount

        return await asyncio.to_thread(operation)

    async def fetch_one(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> dict[str, Any] | None:
        """Busca uma linha e a converte em dicionário."""

        def operation() -> dict[str, Any] | None:
            with self._connect() as connection:
                cursor = connection.cursor()
                row = cursor.execute(sql, parameters).fetchone()
                if row is None:
                    return None
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row, strict=True))

        return await asyncio.to_thread(operation)

    async def fetch_all(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        """Busca todas as linhas e as converte em dicionários."""

        def operation() -> list[dict[str, Any]]:
            with self._connect() as connection:
                cursor = connection.cursor()
                rows = cursor.execute(sql, parameters).fetchall()
                columns = [column[0] for column in cursor.description]
                return [
                    dict(zip(columns, row, strict=True))
                    for row in rows
                ]

        return await asyncio.to_thread(operation)

    async def execute_many(
        self,
        sql: str,
        parameter_rows: Iterable[Sequence[Any]],
    ) -> None:
        """Executa um comando em lote dentro de uma transação."""
        rows = list(parameter_rows)
        if not rows:
            return

        def operation() -> None:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.fast_executemany = True
                cursor.executemany(sql, rows)
                connection.commit()

        await asyncio.to_thread(operation)

    async def transaction(
        self,
        operation: Callable[[pyodbc.Cursor], T],
    ) -> T:
        """Executa uma função dentro de uma transação SQL."""

        def run() -> T:
            connection = self._connect()
            try:
                cursor = connection.cursor()
                result = operation(cursor)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        return await asyncio.to_thread(run)

    async def apply_migrations(self, migrations_dir: Path) -> list[int]:
        """Aplica migrations ainda não registradas em ``schema_migrations``."""

        def operation() -> list[int]:
            applied: list[int] = []
            with self._connect() as connection:
                cursor = connection.cursor()
                for path in sorted(migrations_dir.glob("*.sql")):
                    prefix, _, migration_name = path.stem.partition("_")
                    version = int(prefix)
                    exists = cursor.execute(
                        """
                        SELECT 1
                        FROM nebula.schema_migrations
                        WHERE version = ?
                        """,
                        version,
                    ).fetchone() if self._migration_table_exists(cursor) else None
                    if exists:
                        continue

                    script = path.read_text(encoding="utf-8")
                    for batch in self._split_batches(script):
                        cursor.execute(batch)
                    cursor.execute(
                        """
                        INSERT INTO nebula.schema_migrations (version, name)
                        VALUES (?, ?)
                        """,
                        version,
                        migration_name,
                    )
                    connection.commit()
                    applied.append(version)
            return applied

        versions = await asyncio.to_thread(operation)
        if versions:
            logger.info("Migrations SQL aplicadas", extra={"versions": versions})
        return versions

    @staticmethod
    def _migration_table_exists(cursor: pyodbc.Cursor) -> bool:
        return cursor.execute(
            """
            SELECT OBJECT_ID(N'nebula.schema_migrations', N'U')
            """
        ).fetchval() is not None

    @staticmethod
    def _split_batches(script: str) -> list[str]:
        batches: list[str] = []
        current: list[str] = []
        for line in script.splitlines():
            if line.strip().upper() == "GO":
                batch = "\n".join(current).strip()
                if batch:
                    batches.append(batch)
                current = []
            else:
                current.append(line)
        batch = "\n".join(current).strip()
        if batch:
            batches.append(batch)
        return batches


__all__ = ["Database", "DEFAULT_CONNECTION_STRING"]
