"""Administração local de contas FTP armazenadas no SQL Server."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import re

from ftp.database import Database
from ftp.repositories import UserRepository
from ftp.security import PasswordManager

LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def read_password() -> str:
    password = getpass.getpass("Senha FTP: ")
    if password != getpass.getpass("Confirme a senha: "):
        raise SystemExit("As senhas não coincidem.")
    valid, message = PasswordManager.validate_password_strength(password)
    if not valid:
        raise SystemExit(message)
    return password


async def add_user(repository: UserRepository, login: str) -> None:
    if not LOGIN_PATTERN.fullmatch(login):
        raise SystemExit("Login inválido: use letras, números e underscore.")
    if await repository.get_by_login(login):
        raise SystemExit(f"Usuário {login!r} já existe.")
    password_hash = PasswordManager.hash_password_bcrypt(read_password())
    await repository.create(login, password_hash, f"/{login}")
    print(f"Usuário {login!r} criado.")


async def change_password(repository: UserRepository, login: str) -> None:
    user = await repository.get_by_login(login)
    if user is None:
        raise SystemExit(f"Usuário {login!r} não encontrado.")
    password_hash = PasswordManager.hash_password_bcrypt(read_password())
    await repository.update_password(user.user_id, password_hash)
    print(f"Senha de {login!r} alterada.")


async def list_users(repository: UserRepository) -> None:
    users = await repository.list_users()
    if not users:
        print("Nenhum usuário cadastrado.")
        return
    for user in users:
        state = "ativo" if user["enabled"] else "desativado"
        print(f"{user['login']}\t{state}\t{user['created_at']}")


async def run(arguments: argparse.Namespace) -> None:
    repository = UserRepository(Database())
    if arguments.command == "add":
        await add_user(repository, arguments.login)
    elif arguments.command == "password":
        await change_password(repository, arguments.login)
    elif arguments.command == "list":
        await list_users(repository)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Cria um usuário com senha bcrypt")
    add.add_argument("login")
    password = commands.add_parser("password", help="Altera uma senha")
    password.add_argument("login")
    commands.add_parser("list", help="Lista usuários sem revelar hashes")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
