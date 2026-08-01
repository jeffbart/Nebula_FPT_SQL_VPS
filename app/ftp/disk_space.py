"""Controle de contrapressão quando o staging fica sem espaço livre."""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger("NebulaFTP")


async def wait_for_disk_space(
    staging_dir: Path,
    required_bytes: int,
    minimum_free_bytes: int,
    check_seconds: float,
    timeout_seconds: float,
    filename: str,
    *,
    disk_usage: Callable[[Path], Any] = shutil.disk_usage,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Pausa a gravação até haver reserva ou até expirar o timeout."""
    paused_at: float | None = None
    while disk_usage(staging_dir).free - required_bytes < minimum_free_bytes:
        now = clock()
        if paused_at is None:
            paused_at = now
            logger.warning("Upload FTP pausado por pouco espaço: %s", filename)
        elapsed = now - paused_at
        if timeout_seconds > 0 and elapsed >= timeout_seconds:
            raise OSError(
                "Upload FTP interrompido após exceder o tempo máximo "
                "de espera por espaço livre"
            )
        await sleep(check_seconds)

    if paused_at is not None:
        logger.info(
            "Upload FTP retomado após liberação de espaço: %s espera=%.1fs",
            filename,
            clock() - paused_at,
        )


__all__ = ["wait_for_disk_space"]
