"""Formata o estado da fila de uploads para o Telegram."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .upload_caption import format_size

STATUS_SECTIONS = (
    ("uploading", "📤 Em processamento"),
    ("staging", "⏳ Aguardando"),
    ("failed", "⚠️ Com falha"),
)


def _progress(item: dict[str, Any]) -> str:
    uploaded = int(item.get("uploaded_bytes") or 0)
    total = int(item.get("size_bytes") or 0)
    if not total:
        return format_size(uploaded)
    return f"{format_size(uploaded)} de {format_size(total)}"


def build_queue_message(
    items: list[dict[str, Any]],
    *,
    limit_per_section: int = 20,
) -> str:
    """Agrupa uploads por estado e limita a resposta ao tamanho do Telegram."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item["status"])].append(item)

    if not any(grouped.values()):
        return "✅ A fila de uploads está vazia."

    sections = ["📋 Fila do NebulaFTP"]
    for status, title in STATUS_SECTIONS:
        status_items = grouped.get(status, [])
        if not status_items:
            continue
        lines = [f"{title} ({len(status_items)})"]
        for index, item in enumerate(status_items[:limit_per_section], start=1):
            name = str(item["name"])
            lines.append(f"{index}. {name} — {_progress(item)}")
        omitted = len(status_items) - limit_per_section
        if omitted > 0:
            lines.append(f"… e mais {omitted} arquivo(s).")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)[:4096]


def build_failure_report(items: list[dict[str, Any]]) -> str:
    """Gera um relatório TSV legível e fácil de importar em planilhas."""
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "Relatório de falhas do NebulaFTP",
        f"Gerado em: {generated_at}",
        f"Total: {len(items)}",
        "",
        "node_id\tcaminho\ttamanho\tenviado\ttentativas\tmodificado_em\tultimo_erro",
    ]
    for item in items:
        parent = str(item.get("parent_path") or "/").rstrip("/")
        path = f"{parent}/{item['name']}" if parent else f"/{item['name']}"
        values = (
            item.get("node_id", ""),
            path,
            item.get("size_bytes", 0),
            item.get("uploaded_bytes", 0),
            item.get("attempts", 0),
            item.get("modified_at", ""),
            item.get("last_error", ""),
        )
        clean_values = [
            str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")
            for value in values
        ]
        lines.append("\t".join(clean_values))
    return "\n".join(lines) + "\n"


__all__ = ["build_failure_report", "build_queue_message"]
