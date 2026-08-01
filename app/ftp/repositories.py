"""Repositórios SQL usados pelo servidor FTP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .database import Database


@dataclass(frozen=True, slots=True)
class PermissionRecord:
    virtual_path: str
    readable: bool
    writable: bool


@dataclass(frozen=True, slots=True)
class UserRecord:
    user_id: int
    login: str
    password_hash: str
    password_algorithm: str
    enabled: bool
    permissions: tuple[PermissionRecord, ...]


class UserRepository:
    """Persistência de usuários e permissões FTP."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_by_login(self, login: str) -> UserRecord | None:
        row = await self.database.fetch_one(
            """
            SELECT
                user_id,
                login,
                password_hash,
                password_algorithm,
                enabled
            FROM nebula.users
            WHERE login = ?
            """,
            (login,),
        )
        if row is None:
            return None

        permission_rows = await self.database.fetch_all(
            """
            SELECT virtual_path, readable, writable
            FROM nebula.permissions
            WHERE user_id = ?
            ORDER BY LEN(virtual_path) DESC
            """,
            (row["user_id"],),
        )
        permissions = tuple(
            PermissionRecord(
                virtual_path=item["virtual_path"],
                readable=bool(item["readable"]),
                writable=bool(item["writable"]),
            )
            for item in permission_rows
        )
        return UserRecord(
            user_id=row["user_id"],
            login=row["login"],
            password_hash=row["password_hash"],
            password_algorithm=row["password_algorithm"],
            enabled=bool(row["enabled"]),
            permissions=permissions,
        )

    async def update_password(
        self,
        user_id: int,
        password_hash: str,
        algorithm: str = "bcrypt",
    ) -> None:
        await self.database.execute(
            """
            UPDATE nebula.users
            SET password_hash = ?,
                password_algorithm = ?,
                updated_at = SYSUTCDATETIME()
            WHERE user_id = ?
            """,
            (password_hash, algorithm, user_id),
        )

    async def create(
        self,
        login: str,
        password_hash: str,
        home_path: str,
    ) -> int:
        def operation(cursor: Any) -> int:
            user_id = int(cursor.execute(
                """
                INSERT INTO nebula.users (
                    login,
                    password_hash,
                    password_algorithm
                )
                OUTPUT INSERTED.user_id
                VALUES (?, ?, 'bcrypt')
                """,
                login,
                password_hash,
            ).fetchval())
            cursor.execute(
                """
                INSERT INTO nebula.permissions (
                    user_id,
                    virtual_path,
                    readable,
                    writable
                )
                VALUES (?, ?, 1, 1)
                """,
                user_id,
                home_path,
            )
            return user_id

        return await self.database.transaction(operation)

    async def list_users(self) -> list[dict[str, Any]]:
        return await self.database.fetch_all(
            """
            SELECT user_id, login, enabled, created_at, updated_at
            FROM nebula.users
            ORDER BY login
            """
        )


class NodeRepository:
    """Operações básicas do catálogo persistente."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, parent_path: str, name: str) -> dict[str, Any] | None:
        node = await self.database.fetch_one(
            """
            SELECT
                node_id,
                node_type,
                name,
                parent_path,
                size_bytes,
                status,
                local_path,
                obfuscated_id,
                created_at,
                modified_at
            FROM nebula.nodes
            WHERE parent_path = ? AND name = ?
            """,
            (parent_path, name),
        )
        if node is None:
            return None
        node["parts"] = await self.database.fetch_all(
            """
            SELECT
                part_number,
                telegram_file_id,
                telegram_message_id,
                telegram_chat_id,
                size_bytes,
                chunk_name
            FROM nebula.file_parts
            WHERE node_id = ?
            ORDER BY part_number
            """,
            (node["node_id"],),
        )
        return node

    async def get_by_id(self, node_id: int) -> dict[str, Any] | None:
        row = await self.database.fetch_one(
            """
            SELECT parent_path, name
            FROM nebula.nodes
            WHERE node_id = ?
            """,
            (node_id,),
        )
        if row is None:
            return None
        return await self.get(row["parent_path"], row["name"])

    async def list_children(self, parent_path: str) -> list[dict[str, Any]]:
        return await self.database.fetch_all(
            """
            SELECT
                node_id,
                node_type,
                name,
                parent_path,
                size_bytes,
                status,
                local_path,
                created_at,
                modified_at
            FROM nebula.nodes
            WHERE parent_path = ?
              AND name NOT LIKE '%.partial'
              AND status <> 'deleting'
            ORDER BY node_type, name
            """,
            (parent_path,),
        )

    async def create_directory(self, parent_path: str, name: str) -> int:
        row = await self.database.fetch_one(
            """
            INSERT INTO nebula.nodes (node_type, name, parent_path)
            OUTPUT INSERTED.node_id
            VALUES ('dir', ?, ?)
            """,
            (name, parent_path),
        )
        if row is None:
            raise RuntimeError("Falha ao criar diretório")
        return int(row["node_id"])

    async def stage_file(
        self,
        parent_path: str,
        name: str,
        size_bytes: int,
        local_path: str,
    ) -> int:
        def operation(cursor: Any) -> int:
            existing = cursor.execute(
                """
                SELECT node_id
                FROM nebula.nodes WITH (UPDLOCK, HOLDLOCK)
                WHERE parent_path = ? AND name = ?
                """,
                parent_path,
                name,
            ).fetchone()
            if existing:
                node_id = int(existing[0])
                cursor.execute(
                    """
                    UPDATE nebula.nodes
                    SET node_type = 'file',
                        size_bytes = ?,
                        status = 'staging',
                        local_path = ?,
                        modified_at = SYSUTCDATETIME()
                    WHERE node_id = ?
                    """,
                    size_bytes,
                    local_path,
                    node_id,
                )
                cursor.execute(
                    "DELETE FROM nebula.file_parts WHERE node_id = ?",
                    node_id,
                )
            else:
                node_id = int(cursor.execute(
                    """
                    INSERT INTO nebula.nodes (
                        node_type, name, parent_path, size_bytes, status, local_path
                    )
                    OUTPUT INSERTED.node_id
                    VALUES ('file', ?, ?, ?, 'staging', ?)
                    """,
                    name,
                    parent_path,
                    size_bytes,
                    local_path,
                ).fetchval())
            cursor.execute(
                """
                INSERT INTO nebula.jobs (job_type, node_id)
                VALUES ('upload', ?)
                """,
                node_id,
            )
            return node_id

        return await self.database.transaction(operation)

    async def mark_uploading(self, node_id: int, obfuscated_id: str) -> None:
        await self.database.execute(
            """
            UPDATE nebula.nodes
            SET status = 'uploading',
                obfuscated_id = COALESCE(obfuscated_id, ?),
                modified_at = SYSUTCDATETIME()
            WHERE node_id = ?;

            UPDATE nebula.jobs
            SET status = 'running',
                attempts = attempts + 1,
                locked_at = SYSUTCDATETIME(),
                updated_at = SYSUTCDATETIME()
            WHERE node_id = ? AND job_type = 'upload'
              AND status IN ('pending', 'failed');
            """,
            (obfuscated_id, node_id, node_id),
        )

    async def record_uploaded_part(
        self,
        node_id: int,
        part: dict[str, Any],
    ) -> None:
        """Persiste uma parte antes de liberar seu intervalo no staging."""
        await self.database.execute(
            """
            IF NOT EXISTS (
                SELECT 1
                FROM nebula.file_parts
                WHERE node_id = ? AND part_number = ?
            )
            BEGIN
                INSERT INTO nebula.file_parts (
                    node_id,
                    part_number,
                    telegram_file_id,
                    telegram_message_id,
                    telegram_chat_id,
                    size_bytes,
                    chunk_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            END
            """,
            (
                node_id,
                part["part_number"],
                node_id,
                part["part_number"],
                part["telegram_file_id"],
                part["telegram_message_id"],
                part["telegram_chat_id"],
                part["size_bytes"],
                part["chunk_name"],
            ),
        )

    async def complete_upload(
        self,
        node_id: int,
        size_bytes: int,
        obfuscated_id: str,
    ) -> None:
        def operation(cursor: Any) -> None:
            uploaded_size = cursor.execute(
                """
                SELECT COALESCE(SUM(size_bytes), 0)
                FROM nebula.file_parts
                WHERE node_id = ?
                """,
                node_id,
            ).fetchval()
            if int(uploaded_size) != size_bytes:
                raise RuntimeError(
                    "Partes persistidas não correspondem ao tamanho do arquivo"
                )
            cursor.execute(
                """
                UPDATE nebula.nodes
                SET size_bytes = ?,
                    obfuscated_id = ?,
                    status = 'completed',
                    local_path = NULL,
                    uploaded_at = SYSUTCDATETIME(),
                    modified_at = SYSUTCDATETIME()
                WHERE node_id = ?
                """,
                size_bytes,
                obfuscated_id,
                node_id,
            )
            cursor.execute(
                """
                UPDATE nebula.jobs
                SET status = 'completed', updated_at = SYSUTCDATETIME()
                WHERE node_id = ? AND job_type = 'upload' AND status = 'running'
                """,
                node_id,
            )

        await self.database.transaction(operation)

    async def mark_failed(self, node_id: int, error: str) -> None:
        await self.database.execute(
            """
            UPDATE nebula.nodes
            SET status = 'failed', modified_at = SYSUTCDATETIME()
            WHERE node_id = ?;

            UPDATE nebula.jobs
            SET status = 'failed',
                last_error = ?,
                updated_at = SYSUTCDATETIME()
            WHERE node_id = ? AND job_type = 'upload' AND status = 'running';
            """,
            (node_id, error[:4000], node_id),
        )

    async def delete_node(self, node_id: int) -> None:
        await self.database.execute(
            "DELETE FROM nebula.nodes WHERE node_id = ?",
            (node_id,),
        )

    async def begin_delete(self, node_id: int) -> None:
        def operation(cursor: Any) -> None:
            cursor.execute(
                """
                UPDATE nebula.nodes
                SET status = 'deleting', modified_at = SYSUTCDATETIME()
                WHERE node_id = ?
                """,
                node_id,
            )
            existing = cursor.execute(
                """
                SELECT job_id
                FROM nebula.jobs
                WHERE node_id = ? AND job_type = 'delete'
                  AND status IN ('pending', 'running')
                """,
                node_id,
            ).fetchone()
            if not existing:
                cursor.execute(
                    """
                    INSERT INTO nebula.jobs (job_type, node_id)
                    VALUES ('delete', ?)
                    """,
                    node_id,
                )

        await self.database.transaction(operation)

    async def postpone_delete(self, node_id: int, error: str) -> None:
        await self.database.execute(
            """
            UPDATE nebula.jobs
            SET status = 'pending',
                attempts = attempts + 1,
                available_at = DATEADD(second, 30, SYSUTCDATETIME()),
                last_error = ?,
                updated_at = SYSUTCDATETIME()
            WHERE node_id = ? AND job_type = 'delete';
            """,
            (error[:4000], node_id),
        )

    async def rename(
        self,
        node_id: int,
        parent_path: str,
        name: str,
    ) -> None:
        await self.database.execute(
            """
            UPDATE nebula.nodes
            SET parent_path = ?,
                name = ?,
                modified_at = SYSUTCDATETIME()
            WHERE node_id = ?
            """,
            (parent_path, name, node_id),
        )

    async def delete_empty_directory(self, node_id: int, full_path: str) -> bool:
        def operation(cursor: Any) -> bool:
            child = cursor.execute(
                "SELECT TOP (1) 1 FROM nebula.nodes WHERE parent_path = ?",
                full_path,
            ).fetchone()
            if child:
                return False
            cursor.execute(
                "DELETE FROM nebula.nodes WHERE node_id = ? AND node_type = 'dir'",
                node_id,
            )
            return cursor.rowcount == 1

        return await self.database.transaction(operation)

    async def recover_uploads(self) -> list[dict[str, Any]]:
        return await self.database.fetch_all(
            """
            SELECT
                n.node_id,
                n.name,
                n.parent_path,
                n.size_bytes,
                n.local_path
            FROM nebula.nodes AS n
            WHERE n.node_type = 'file'
              AND n.status IN ('staging', 'uploading', 'failed')
              AND n.local_path IS NOT NULL
            ORDER BY n.modified_at
            """
        )

    async def get_upload_queue_status(self) -> list[dict[str, Any]]:
        """Lista uploads pendentes, ativos e com falha com seu progresso."""
        return await self.database.fetch_all(
            """
            SELECT
                n.node_id,
                n.name,
                n.parent_path,
                n.status,
                n.size_bytes,
                COALESCE(SUM(p.size_bytes), 0) AS uploaded_bytes,
                n.modified_at
            FROM nebula.nodes AS n
            LEFT JOIN nebula.file_parts AS p ON p.node_id = n.node_id
            WHERE n.node_type = 'file'
              AND n.status IN ('staging', 'uploading', 'failed')
            GROUP BY
                n.node_id,
                n.name,
                n.parent_path,
                n.status,
                n.size_bytes,
                n.modified_at
            ORDER BY
                CASE n.status
                    WHEN 'uploading' THEN 0
                    WHEN 'staging' THEN 1
                    ELSE 2
                END,
                n.modified_at
            """
        )

    async def get_failed_upload_report(self) -> list[dict[str, Any]]:
        """Retorna detalhes das falhas para exportação pelo bot."""
        return await self.database.fetch_all(
            """
            SELECT
                n.node_id,
                n.name,
                n.parent_path,
                n.size_bytes,
                n.modified_at,
                COALESCE(parts.uploaded_bytes, 0) AS uploaded_bytes,
                COALESCE(job.attempts, 0) AS attempts,
                COALESCE(job.last_error, '') AS last_error
            FROM nebula.nodes AS n
            OUTER APPLY (
                SELECT SUM(p.size_bytes) AS uploaded_bytes
                FROM nebula.file_parts AS p
                WHERE p.node_id = n.node_id
            ) AS parts
            OUTER APPLY (
                SELECT TOP (1) j.attempts, j.last_error
                FROM nebula.jobs AS j
                WHERE j.node_id = n.node_id
                  AND j.job_type = 'upload'
                ORDER BY j.job_id DESC
            ) AS job
            WHERE n.node_type = 'file'
              AND n.status = 'failed'
            ORDER BY n.modified_at, n.node_id
            """
        )

    async def schedule_failed_deletions(self) -> list[int]:
        """Marca todos os uploads com falha para exclusão recuperável."""
        def operation(cursor: Any) -> list[int]:
            rows = cursor.execute(
                """
                UPDATE nebula.nodes
                SET status = 'deleting', modified_at = SYSUTCDATETIME()
                OUTPUT INSERTED.node_id
                WHERE node_type = 'file' AND status = 'failed'
                """
            ).fetchall()
            node_ids = [int(row[0]) for row in rows]
            if node_ids:
                cursor.execute(
                    """
                    INSERT INTO nebula.jobs (job_type, node_id)
                    SELECT 'delete', n.node_id
                    FROM nebula.nodes AS n
                    WHERE n.status = 'deleting'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM nebula.jobs AS j
                          WHERE j.node_id = n.node_id
                            AND j.job_type = 'delete'
                            AND j.status IN ('pending', 'running')
                      )
                    """
                )
            return node_ids

        return await self.database.transaction(operation)

    async def recover_deletions(self) -> list[int]:
        rows = await self.database.fetch_all(
            """
            SELECT DISTINCT node_id
            FROM nebula.jobs
            WHERE job_type = 'delete'
              AND status IN ('pending', 'failed')
              AND available_at <= SYSUTCDATETIME()
              AND node_id IS NOT NULL
            ORDER BY node_id
            """
        )
        return [int(row["node_id"]) for row in rows]


__all__ = [
    "NodeRepository",
    "PermissionRecord",
    "UserRecord",
    "UserRepository",
]
