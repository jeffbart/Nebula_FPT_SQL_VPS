"""Formata a legenda das partes enviadas ao Telegram."""

from __future__ import annotations

import math


def format_size(size_bytes: int) -> str:
    """Retorna um tamanho legível com separador decimal brasileiro."""
    units = ("bytes", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    unit = units[0]

    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024

    if unit == "bytes":
        amount = str(size_bytes)
    elif value >= 10 or value.is_integer():
        amount = f"{value:.0f}"
    else:
        amount = f"{value:.1f}".replace(".", ",")
    return f"{amount} {unit}"


def build_upload_caption(
    filename: str,
    part_number: int,
    chunk_size: int,
    uploaded_offset: int,
    total_size: int,
    configured_chunk_size: int,
) -> str:
    """Monta a legenda com arquivo, parte atual e progresso acumulado."""
    total_parts = math.ceil(total_size / configured_chunk_size)
    current_part = part_number + 1
    width = max(2, len(str(total_parts)))
    uploaded_size = min(uploaded_offset + chunk_size, total_size)
    return (
        f"{filename}\n"
        f"({current_part:0{width}d} de {total_parts:0{width}d}) "
        f"({format_size(uploaded_size)} de {format_size(total_size)})"
    )


__all__ = ["build_upload_caption", "format_size"]
