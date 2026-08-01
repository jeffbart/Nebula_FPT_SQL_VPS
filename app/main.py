"""Ponto de entrada do NebulaFTP para Windows."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import signal
import ssl
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

import aiofiles
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from pyrogram.handlers import MessageHandler

from ftp import SQLServerPathIO, SQLServerUserManager, Server
from ftp.common import DELETE_QUEUE, UPLOAD_QUEUE
from ftp.database import Database
from ftp.repositories import NodeRepository, UserRepository
from ftp.queue_status import build_failure_report, build_queue_message
from ftp.staging_space import release_uploaded_range
from ftp.upload_caption import build_upload_caption

load_dotenv(Path(os.environ.get("NEBULA_ENV_FILE", ".env")))

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE_MB", "64")) * 1024 * 1024
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
MAX_STAGING_AGE = int(os.environ.get("MAX_STAGING_AGE", "3600"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "4"))
STAGING_DIR = Path(os.environ.get("STAGING_DIR", "staging")).resolve()
ACTIVE_UPLOADS: set[str] = set()

logger = logging.getLogger("NebulaFTP")


def configure_logging() -> None:
    log_file = Path(os.environ.get("LOG_FILE", "nebula.log")).resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(os.environ.get("LOG_MAX_SIZE_MB", "10")) * 1024 * 1024,
        backupCount=int(os.environ.get("LOG_BACKUP_COUNT", "5")),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


async def garbage_collector() -> None:
    """Remove staging abandonado sem tocar em uploads ativos."""
    while True:
        cutoff = time.time() - MAX_STAGING_AGE
        try:
            for path in STAGING_DIR.rglob("*"):
                path_string = str(path)
                if (
                    not path.is_file()
                    or path_string in ACTIVE_UPLOADS
                ):
                    continue
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    logger.warning("Staging expirado removido: %s", path)
        except Exception:
            logger.exception("Falha no garbage collector")
        await asyncio.sleep(600)


async def recover_upload_queue(repository: NodeRepository) -> None:
    for node in await repository.recover_uploads():
        local_path = Path(node["local_path"])
        if not local_path.exists():
            await repository.mark_failed(
                node["node_id"],
                "Arquivo de staging ausente durante recuperação",
            )
            continue
        await UPLOAD_QUEUE.put(
            {
                "node_id": node["node_id"],
                "path": str(local_path),
                "filename": node["name"],
                "parent": node["parent_path"],
                "size": node["size_bytes"],
            }
        )

    for node_id in await repository.recover_deletions():
        await DELETE_QUEUE.put(node_id)


async def delete_uploaded_parts(bot: Client, parts: list[dict]) -> None:
    by_chat: dict[int, list[int]] = {}
    for part in parts:
        by_chat.setdefault(part["telegram_chat_id"], []).append(
            part["telegram_message_id"]
        )
    for chat_id, message_ids in by_chat.items():
        for offset in range(0, len(message_ids), 100):
            await bot.delete_messages(chat_id, message_ids[offset : offset + 100])


async def deletion_worker(bot: Client, repository: NodeRepository) -> None:
    while True:
        node_id = await DELETE_QUEUE.get()
        try:
            node = await repository.get_by_id(node_id)
            if node is None:
                continue
            await delete_uploaded_parts(bot, node["parts"])
            if node.get("local_path"):
                Path(node["local_path"]).unlink(missing_ok=True)
            await repository.delete_node(node_id)
            logger.info("Exclusão Telegram concluída para node_id=%s", node_id)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            logger.exception("Retry de exclusão falhou para node_id=%s", node_id)
            await repository.postpone_delete(node_id, str(exception))
            asyncio.get_running_loop().call_later(
                30,
                DELETE_QUEUE.put_nowait,
                node_id,
            )
        finally:
            DELETE_QUEUE.task_done()


async def upload_worker(
    bot: Client,
    target_chat_id: int,
    repository: NodeRepository,
    worker_id: int,
) -> None:
    logger.info("Worker de upload %s iniciado", worker_id)
    while True:
        task = await UPLOAD_QUEUE.get()
        local_path = Path(task["path"])
        node_id = int(task["node_id"])
        ACTIVE_UPLOADS.add(str(local_path))
        try:
            if task["filename"].endswith(".partial"):
                continue
            if not local_path.exists():
                raise FileNotFoundError(local_path)
            size = local_path.stat().st_size
            if not size:
                raise ValueError("Upload vazio")

            node = await repository.get_by_id(node_id)
            if node is None:
                raise RuntimeError(f"Nó de upload ausente: {node_id}")
            existing_parts = sorted(
                node["parts"], key=lambda item: item["part_number"]
            )
            for expected, part in enumerate(existing_parts):
                if part["part_number"] != expected:
                    raise RuntimeError("Sequência de partes persistidas inválida")

            file_uuid = str(node.get("obfuscated_id") or uuid.uuid4())
            await repository.mark_uploading(node_id, file_uuid)
            uploaded_offset = sum(part["size_bytes"] for part in existing_parts)
            if uploaded_offset > size:
                raise RuntimeError("Partes persistidas excedem o arquivo local")

            async with aiofiles.open(local_path, "rb") as source:
                await source.seek(uploaded_offset)
                part_number = len(existing_parts)
                while chunk := await source.read(CHUNK_SIZE):
                    chunk_name = f"{file_uuid}.part_{part_number:03d}"
                    document = io.BytesIO(chunk)
                    document.name = chunk_name
                    sent_message = None
                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            document.seek(0)
                            sent_message = await bot.send_document(
                                chat_id=target_chat_id,
                                document=document,
                                file_name=chunk_name,
                                caption=build_upload_caption(
                                    filename=task["filename"],
                                    part_number=part_number,
                                    chunk_size=len(chunk),
                                    uploaded_offset=uploaded_offset,
                                    total_size=size,
                                    configured_chunk_size=CHUNK_SIZE,
                                ),
                            )
                            break
                        except FloodWait as exception:
                            await asyncio.sleep(exception.value + 2)
                        except RPCError:
                            logger.exception(
                                "Telegram recusou parte %s; tentativa %s",
                                part_number,
                                attempt,
                            )
                            await asyncio.sleep(2**attempt)
                    if sent_message is None:
                        raise RuntimeError(f"Falha ao enviar parte {part_number}")
                    part = {
                        "part_number": part_number,
                        "telegram_file_id": sent_message.document.file_id,
                        "telegram_message_id": sent_message.id,
                        "telegram_chat_id": target_chat_id,
                        "size_bytes": len(chunk),
                        "chunk_name": chunk_name,
                    }
                    try:
                        await repository.record_uploaded_part(node_id, part)
                    except Exception:
                        try:
                            await bot.delete_messages(target_chat_id, sent_message.id)
                        except Exception:
                            logger.exception(
                                "Falha ao remover parte não persistida do Telegram"
                            )
                        raise

                    if release_uploaded_range(
                        local_path,
                        uploaded_offset,
                        len(chunk),
                    ):
                        logger.info(
                            "Espaço local liberado: %s parte=%s bytes=%s",
                            task["filename"],
                            part_number,
                            len(chunk),
                        )
                    else:
                        logger.warning(
                            "Volume não liberou a parte %s de %s; "
                            "o arquivo completo será apagado ao final",
                            part_number,
                            task["filename"],
                        )
                    uploaded_offset += len(chunk)
                    part_number += 1

            await repository.complete_upload(
                node_id,
                size,
                file_uuid,
            )
            local_path.unlink(missing_ok=True)
            logger.info("Upload concluído: %s", task["filename"])
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            logger.exception("Upload falhou: %s", task["filename"])
            await repository.mark_failed(node_id, str(exception))
            if local_path.exists():
                asyncio.get_running_loop().call_later(
                    30,
                    UPLOAD_QUEUE.put_nowait,
                    task,
                )
        finally:
            ACTIVE_UPLOADS.discard(str(local_path))
            UPLOAD_QUEUE.task_done()


async def resolve_channel(bot: Client) -> int:
    raw_chat = os.environ.get("CHAT_ID")
    if not raw_chat:
        raise RuntimeError("CHAT_ID não configurado")
    chat_id: int | str = int(raw_chat) if raw_chat.lstrip("-").isdigit() else raw_chat
    chat = await bot.get_chat(chat_id)
    logger.info("Canal Telegram validado: %s", chat.title)
    return chat.id


async def queue_command_handler(
    bot: Client,
    message,
    repository: NodeRepository,
    target_chat_id: int,
) -> None:
    """Responde ao comando /queue somente no canal configurado."""
    if message.chat.id != target_chat_id:
        return
    try:
        await message.delete()
    except RPCError:
        logger.warning("Não foi possível apagar o comando /queue do canal")

    try:
        items = await repository.get_upload_queue_status()
        response = build_queue_message(items)
    except Exception:
        logger.exception("Falha ao consultar a fila pelo comando /queue")
        response = "⚠️ Não foi possível consultar a fila de uploads."
    await bot.send_message(target_chat_id, response)


async def fetch_command_handler(
    bot: Client,
    message,
    repository: NodeRepository,
    target_chat_id: int,
) -> None:
    """Envia um relatório das falhas sem gravá-lo no disco da VPS."""
    if message.chat.id != target_chat_id:
        return
    try:
        await message.delete()
    except RPCError:
        logger.warning("Não foi possível apagar o comando /fetch do canal")

    try:
        items = await repository.get_failed_upload_report()
        report = io.BytesIO(build_failure_report(items).encode("utf-8-sig"))
        report.name = time.strftime("nebulaftp_falhas_%Y%m%d_%H%M%S.txt")
        await bot.send_document(
            chat_id=target_chat_id,
            document=report,
            file_name=report.name,
            caption=f"Relatório de falhas do NebulaFTP — {len(items)} registro(s)",
        )
    except Exception:
        logger.exception("Falha ao gerar o relatório pelo comando /fetch")
        await bot.send_message(
            target_chat_id,
            "⚠️ Não foi possível gerar o relatório de falhas.",
        )


def configure_shutdown(loop: asyncio.AbstractEventLoop, event: asyncio.Event) -> None:
    def stop(*_) -> None:
        loop.call_soon_threadsafe(event.set)

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop)
        except NotImplementedError:
            signal.signal(signal_name, stop)


def build_tls_context() -> ssl.SSLContext:
    certificate = Path(os.environ["FTP_CERT_PATH"]).resolve()
    private_key = Path(os.environ["FTP_KEY_PATH"]).resolve()
    if not certificate.is_file() or not private_key.is_file():
        raise RuntimeError("Certificado ou chave FTPS não encontrado")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, private_key)
    return context


def passive_port_range() -> range:
    value = os.environ.get("PASSIVE_PORTS", "60000-60049")
    first, separator, last = value.partition("-")
    if not separator:
        raise ValueError("PASSIVE_PORTS deve usar o formato início-fim")
    start_port, end_port = int(first), int(last)
    if not (1024 <= start_port <= end_port <= 65535):
        raise ValueError("Intervalo de portas passivas inválido")
    return range(start_port, end_port + 1)


async def main() -> None:
    configure_logging()
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    database = Database()
    node_repository = NodeRepository(database)
    user_repository = UserRepository(database)

    bot_token = (os.environ.get("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN não configurado")
    bot = Client(
        "NebulaFTP",
        api_id=int(os.environ["API_ID"]),
        api_hash=os.environ["API_HASH"],
        bot_token=bot_token,
        workdir=str(Path(os.environ.get("DATA_DIR", "data")).resolve()),
    )
    await bot.start()
    target_chat_id = await resolve_channel(bot)

    async def handle_queue_command(client, message) -> None:
        await queue_command_handler(
            client,
            message,
            node_repository,
            target_chat_id,
        )

    async def handle_fetch_command(client, message) -> None:
        await fetch_command_handler(
            client,
            message,
            node_repository,
            target_chat_id,
        )

    bot.add_handler(
        MessageHandler(
            handle_queue_command,
            filters.command("queue") & filters.chat(target_chat_id),
        )
    )
    bot.add_handler(
        MessageHandler(
            handle_fetch_command,
            filters.command("fetch") & filters.chat(target_chat_id),
        )
    )

    SQLServerPathIO.repository = node_repository
    SQLServerPathIO.telegram = bot
    SQLServerPathIO.staging_dir = STAGING_DIR
    server = Server(
        SQLServerUserManager(user_repository),
        SQLServerPathIO,
        tls_context=build_tls_context(),
        tls_required=True,
        passive_ports=passive_port_range(),
        passive_host=os.environ.get("PASSIVE_HOST"),
    )

    await recover_upload_queue(node_repository)
    background_tasks = [asyncio.create_task(garbage_collector())]
    background_tasks.append(
        asyncio.create_task(deletion_worker(bot, node_repository))
    )
    background_tasks.extend(
        asyncio.create_task(
            upload_worker(bot, target_chat_id, node_repository, worker_id)
        )
        for worker_id in range(1, MAX_WORKERS + 1)
    )

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "2121"))
    await server.start(host, port)
    logger.info("NebulaFTP ouvindo em %s:%s", host, port)

    stop_event = asyncio.Event()
    configure_shutdown(asyncio.get_running_loop(), stop_event)
    try:
        await stop_event.wait()
    finally:
        await server.close()
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
