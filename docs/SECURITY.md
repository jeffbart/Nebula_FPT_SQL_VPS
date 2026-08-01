# Segurança

## Dados que nunca devem entrar no Git

- `config/.env` e qualquer `.env` real;
- `API_HASH`, `BOT_TOKEN` e connection strings com senha;
- arquivos `*.session*` do Telegram;
- chaves `*.key`, `*.pem`, `*.pfx` e `*.p12`;
- certificados e diretórios `certs/` locais;
- logs, staging, backups e banco exportado;
- ambiente `venv/`.

O `.gitignore` da raiz cobre esses itens. Ele não substitui uma inspeção antes
do commit.

## FTPS

- exija TLS explícito;
- use TLS 1.2 ou superior;
- proteja controle e dados com `PROT P`;
- substitua certificados autoassinados em produção;
- libere apenas a porta de controle e a faixa passiva;
- mantenha a chave privada acessível somente à conta do serviço.

## SQL Server

- prefira autenticação integrada do Windows;
- não exponha a porta 1433 à internet;
- conceda à conta do serviço somente permissões necessárias no schema `nebula`;
- proteja e teste backups regularmente.

## Telegram

O bot precisa publicar e apagar mensagens no canal privado. Se qualquer token
for publicado, revogue-o no BotFather antes de apenas remover o commit.

