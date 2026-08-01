"""Componentes do NebulaFTP carregados sob demanda."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PathIOError",
    "Permission",
    "SQLServerPathIO",
    "SQLServerUserManager",
    "Server",
    "UPLOAD_QUEUE",
    "User",
]


def __getattr__(name: str) -> Any:
    if name in {"Server", "SQLServerUserManager", "User", "Permission"}:
        from .server import Permission, Server, SQLServerUserManager, User

        return {
            "Server": Server,
            "SQLServerUserManager": SQLServerUserManager,
            "User": User,
            "Permission": Permission,
        }[name]
    if name == "SQLServerPathIO":
        from .pathio import SQLServerPathIO

        return SQLServerPathIO
    if name == "UPLOAD_QUEUE":
        from .common import UPLOAD_QUEUE

        return UPLOAD_QUEUE
    if name == "PathIOError":
        from .errors import PathIOError

        return PathIOError
    raise AttributeError(name)
