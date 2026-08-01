"""Cria um usuário FTP com senha bcrypt sem exibir o segredo."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import re

from ftp.database import Database
from ftp.repositories import UserRepository
from ftp.security import PasswordManager

LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


async def create_user(login: str) -> None:
    if not LOGIN_PATTERN.fullmatch(login):
        raise SystemExit("Login deve conter apenas letras, números e underscore.")

    repository = UserRepository(Database())
    if await repository.get_by_login(login):
        raise SystemExit(f"Usuário {login!r} já existe.")

    password = getpass.getpass("Senha FTP: ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        raise SystemExit("As senhas não coincidem.")
    valid, message = PasswordManager.validate_password_strength(password)
    if not valid:
        raise SystemExit(message)

    password_hash = PasswordManager.hash_password_bcrypt(password)
    await repository.create(login, password_hash, f"/{login}")
    print(f"Usuário {login!r} criado com senha bcrypt.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("login")
    arguments = parser.parse_args()
    asyncio.run(create_user(arguments.login))


if __name__ == "__main__":
    main()

