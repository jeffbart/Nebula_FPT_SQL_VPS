"""Aplica migrations SQL usando a identidade Windows do processo atual."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ftp.database import Database


async def main() -> None:
    migrations = Path(__file__).resolve().parents[1] / "ftp" / "migrations"
    versions = await Database().apply_migrations(migrations)
    if versions:
        print("Migrations aplicadas:", ", ".join(map(str, versions)))
    else:
        print("Banco já está atualizado.")


if __name__ == "__main__":
    asyncio.run(main())

