"""Sistema de arquivos virtual persistido no SQL Server."""

from __future__ import annotations

import os
import shutil
from asyncio import CancelledError
from collections import namedtuple
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path, PurePosixPath
from sys import exc_info
from time import time
from typing import Any
from uuid import uuid4

import aiofiles

from .common import DELETE_QUEUE, UPLOAD_QUEUE
from .errors import PathIOError
from .repositories import NodeRepository

__all__ = ("AbstractPathIO", "PathIONursery", "SQLServerPathIO")


def universal_exception(coroutine):
    """Converte falhas internas em erros compreendidos pelo servidor FTP."""

    @wraps(coroutine)
    async def wrapper(*args, **kwargs):
        try:
            return await coroutine(*args, **kwargs)
        except (CancelledError, NotImplementedError, StopAsyncIteration):
            raise
        except Exception as exception:
            raise PathIOError(reason=exc_info()) from exception

    return wrapper


class PathIONursery:
    def __init__(self, factory):
        self.factory = factory
        self.state = None

    def __call__(self, *args, **kwargs):
        instance = self.factory(*args, state=self.state, **kwargs)
        if self.state is None:
            self.state = instance.state
        return instance


class AbstractPathIO:
    def __init__(self, connection=None):
        self.connection = connection


class Node:
    """Representação em memória de um item do catálogo."""

    def __init__(
        self,
        *,
        node_id: int | None,
        node_type: str,
        name: str,
        parent_path: str,
        size_bytes: int = 0,
        status: str = "completed",
        local_path: str | None = None,
        created_at: datetime | None = None,
        modified_at: datetime | None = None,
        parts: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> None:
        self.node_id = node_id
        self.type = node_type
        self.name = name
        self.parent = parent_path
        self.size = size_bytes
        self.status = status
        self.local_path = local_path
        self.ctime = _timestamp(created_at)
        self.mtime = _timestamp(modified_at)
        self.parts = parts or []

    @property
    def path(self) -> str:
        return str(PurePosixPath(self.parent) / self.name)


def _timestamp(value: datetime | None) -> int:
    if value is None:
        return int(time())
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


class SQLServerMemoryIO:
    def __init__(
        self,
        node: Node,
        mode: str,
        telegram,
        repository: NodeRepository,
        staging_dir: Path,
    ) -> None:
        self.node = node
        self.mode = mode
        self.telegram = telegram
        self.repository = repository
        self.staging_dir = staging_dir
        self.offset = 0
        self.registered = node.node_id is not None and node.local_path is not None
        self.minimum_free_bytes = int(
            float(os.environ.get("MIN_FREE_DISK_GB", "10")) * 1024**3
        )
        self.local_path = (
            Path(node.local_path)
            if node.local_path
            else staging_dir / f"{uuid4().hex}_{node.name}"
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, *_):
        if exception_type is not None and not self.registered:
            self.local_path.unlink(missing_ok=True)
        return None

    async def seek(self, offset=0):
        self.offset = offset

    async def write_stream(self, stream):
        file_mode = "r+b" if self.offset and self.local_path.exists() else "wb"
        async with aiofiles.open(self.local_path, file_mode) as output:
            if self.offset:
                await output.seek(self.offset)
            async for data in stream.iter_by_block(1024 * 1024):
                free_bytes = shutil.disk_usage(self.staging_dir).free
                if free_bytes - len(data) < self.minimum_free_bytes:
                    raise OSError(
                        "Upload interrompido para preservar espaço livre no disco"
                    )
                await output.write(data)
            await output.flush()

        size = self.local_path.stat().st_size
        node_id = await self.repository.stage_file(
            self.node.parent,
            self.node.name,
            size,
            str(self.local_path),
        )
        self.node.node_id = node_id
        self.node.size = size
        self.node.local_path = str(self.local_path)
        self.node.status = "staging"
        self.registered = True

        if not self.node.name.endswith(".partial") and size:
            await UPLOAD_QUEUE.put(
                {
                    "node_id": node_id,
                    "path": str(self.local_path),
                    "filename": self.node.name,
                    "parent": self.node.parent,
                    "size": size,
                }
            )

    async def iter_by_block(self, block_size):
        if self.node.local_path and Path(self.node.local_path).exists():
            async with aiofiles.open(self.node.local_path, "rb") as source:
                await source.seek(self.offset)
                while data := await source.read(block_size):
                    yield data
            return

        current_position = 0
        for part in self.node.parts:
            part_size = int(part["size_bytes"])
            part_end = current_position + part_size
            if part_end <= self.offset:
                current_position = part_end
                continue
            local_offset = max(0, self.offset - current_position)
            from .tg import File

            remote_file = File(part["telegram_file_id"], self.telegram)
            async for data in remote_file.stream(offset=local_offset):
                yield data
            current_position = part_end


class SQLServerPathIO(AbstractPathIO):
    repository: NodeRepository | None = None
    telegram = None
    staging_dir = Path(os.environ.get("STAGING_DIR", "staging")).resolve()
    Stats = namedtuple(
        "Stats",
        ("st_size", "st_ctime", "st_mtime", "st_nlink", "st_mode"),
    )

    def __init__(self, *args, state=None, cwd=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.repository is None:
            raise RuntimeError("SQLServerPathIO não foi configurado")
        self.cwd = PurePosixPath(cwd or "/")
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state(self):
        return []

    def _absolute(self, path) -> PurePosixPath:
        value = PurePosixPath(path)
        if not value.is_absolute():
            value = self.cwd / value
        resolved = PurePosixPath("/")
        for part in value.parts[1:]:
            resolved = resolved.parent if part == ".." else resolved / part
        return resolved

    @staticmethod
    def _split(path: PurePosixPath) -> tuple[str, str]:
        normalized = path.as_posix().rstrip("/") or "/"
        value = PurePosixPath(normalized)
        return value.parent.as_posix(), value.name

    async def get_node(self, path) -> Node | None:
        absolute = self._absolute(path)
        if absolute == PurePosixPath("/"):
            return Node(
                node_id=None,
                node_type="dir",
                name="",
                parent_path="/",
            )
        parent, name = self._split(absolute)
        record = await self.repository.get(parent, name)
        return Node(**record) if record else None

    @universal_exception
    async def exists(self, path):
        return await self.get_node(path) is not None

    @universal_exception
    async def is_dir(self, path):
        node = await self.get_node(path)
        return node is not None and node.type == "dir"

    @universal_exception
    async def is_file(self, path):
        node = await self.get_node(path)
        return node is not None and node.type == "file"

    @universal_exception
    async def mkdir(self, path, *, exist_ok=False):
        absolute = self._absolute(path)
        existing = await self.get_node(absolute)
        if existing:
            if not exist_ok:
                raise FileExistsError(absolute)
            return
        parent, name = self._split(absolute)
        await self.repository.create_directory(parent, name)

    @universal_exception
    async def rmdir(self, path):
        absolute = self._absolute(path)
        node = await self.get_node(absolute)
        if node is None or node.node_id is None:
            raise FileNotFoundError(absolute)
        deleted = await self.repository.delete_empty_directory(
            node.node_id,
            absolute.as_posix(),
        )
        if not deleted:
            raise OSError("diretório não está vazio")

    async def _delete_remote_parts(self, node: Node) -> None:
        by_chat: dict[int, list[int]] = {}
        for part in node.parts:
            by_chat.setdefault(int(part["telegram_chat_id"]), []).append(
                int(part["telegram_message_id"])
            )
        for chat_id, message_ids in by_chat.items():
            for offset in range(0, len(message_ids), 100):
                await self.telegram.delete_messages(
                    chat_id,
                    message_ids[offset : offset + 100],
                )

    @universal_exception
    async def unlink(self, path):
        node = await self.get_node(self._absolute(path))
        if node is None or node.node_id is None:
            raise FileNotFoundError(path)
        await self.repository.begin_delete(node.node_id)
        try:
            if node.parts:
                await self._delete_remote_parts(node)
            if node.local_path:
                Path(node.local_path).unlink(missing_ok=True)
            await self.repository.delete_node(node.node_id)
        except Exception as exception:
            await self.repository.postpone_delete(node.node_id, str(exception))
            await DELETE_QUEUE.put(node.node_id)
            raise

    def list(self, path):
        absolute = self._absolute(path)

        async def iterator():
            records = await self.repository.list_children(absolute.as_posix())
            for record in records:
                yield absolute / record["name"]

        return iterator()

    @universal_exception
    async def stat(self, path):
        node = await self.get_node(self._absolute(path))
        if node is None:
            raise FileNotFoundError(path)
        mode = (0x8000 | 0o666) if node.type == "file" else (0x4000 | 0o777)
        return self.Stats(node.size, node.ctime, node.mtime, 1, mode)

    @universal_exception
    async def open(self, path, mode="rb", *_, **__):
        absolute = self._absolute(path)
        parent, name = self._split(absolute)
        node = await self.get_node(absolute)
        if mode == "rb":
            if node is None:
                raise FileNotFoundError(path)
        elif node is None:
            node = Node(
                node_id=None,
                node_type="file",
                name=name,
                parent_path=parent,
                status="staging",
            )
        elif mode == "wb" and node.parts:
            await self._delete_remote_parts(node)
            await self.repository.delete_node(node.node_id)
            node = Node(
                node_id=None,
                node_type="file",
                name=name,
                parent_path=parent,
                status="staging",
            )
        return SQLServerMemoryIO(
            node,
            mode,
            self.telegram,
            self.repository,
            self.staging_dir,
        )

    @universal_exception
    async def rename(self, source, destination):
        source_path = self._absolute(source)
        destination_path = self._absolute(destination)
        node = await self.get_node(source_path)
        if node is None or node.node_id is None:
            raise FileNotFoundError(source)

        destination_parent, destination_name = self._split(destination_path)
        await self.repository.rename(
            node.node_id,
            destination_parent,
            destination_name,
        )
        if node.name.endswith(".partial") and not destination_name.endswith(".partial"):
            if node.local_path and Path(node.local_path).exists():
                await UPLOAD_QUEUE.put(
                    {
                        "node_id": node.node_id,
                        "path": node.local_path,
                        "filename": destination_name,
                        "parent": destination_parent,
                        "size": node.size,
                    }
                )
