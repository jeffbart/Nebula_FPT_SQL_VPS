# Nebula FTP SQL VPS

Vertente do [NebulaFTP](https://github.com/jeffbart/NebulaFTP) preparada para
Windows VPS, Microsoft SQL Server e FTPS explícito. O Telegram armazena o
conteúdo multipartes; o SQL Server mantém catálogo, pastas, usuários, estados e
referências das mensagens.

> Nome do repositório planejado: `Nebula_FPT_SQL_VPS`.

## Destaques

- Windows VPS com execução Python nativa;
- SQL Server via ODBC Driver 18 e autenticação integrada;
- FTPS explícito, TLS 1.2+, portas passivas configuráveis;
- senhas FTP protegidas com bcrypt;
- catálogo e pastas persistentes;
- upload multipartes para canal privado do Telegram;
- retomada de upload após falha ou reinício;
- remoção das mensagens do Telegram ao excluir arquivos;
- liberação progressiva do espaço do staging em NTFS compatível;
- compatibilidade validada com WinSCP; rclone ainda em validação.

## Estrutura

```text
NebulaFTP\
├── app\                 código Python
├── config\              exemplo público e .env privado
├── certs\               certificado/chave locais, ignorados pelo Git
├── data\                sessão Telegram, ignorada
├── logs\                logs locais, ignorados
├── staging\             uploads temporários, ignorados
├── backups\             backups locais, ignorados
├── venv\                ambiente Python, ignorado
└── iniciar_nebulaftp_vps.bat
```

## Fluxo de upload e uso de disco

1. O cliente envia um arquivo por FTPS para o staging.
2. O worker lê uma parte de tamanho configurável.
3. O bot confirma o envio da parte ao Telegram.
4. A referência da mensagem é persistida no SQL Server.
5. O intervalo correspondente é desalocado do arquivo esparso no Windows.
6. Ao final, o catálogo é marcado como concluído e o arquivo lógico é removido.

A ordem Telegram → SQL → liberação local evita perder dados. Em NTFS, o arquivo
mantém o tamanho lógico durante o processamento, mas os clusters confirmados
podem ser devolvidos progressivamente ao disco. Se o volume não aceitar arquivos
esparsos, o upload continua e o temporário completo é apagado ao final.

## Início rápido

1. Instale Python 3.11 x64, SQL Server e ODBC Driver 18.
2. Crie o banco e aplique `app/ftp/migrations/001_initial.sql`.
3. Copie `config/.env.vps.example` para `config/.env`.
4. Preencha Telegram, banco, certificado, portas e caminhos.
5. Execute `app/scripts/deploy_vps.ps1`.
6. Crie um usuário FTP com `app/accounts_manager.py`.
7. Execute `iniciar_nebulaftp_vps.bat` na raiz.

Consulte [Instalação](docs/INSTALLATION.md) para o procedimento completo.

## Segurança

O `.gitignore` exclui `.env`, sessões Telegram, chaves privadas, certificados,
logs, staging, backups, ambiente virtual e pacotes locais. Antes de publicar,
sempre execute:

```powershell
git status --short
git check-ignore -v config\.env certs\nebulaftp.key data\NebulaFTP.session
```

Nunca publique token de bot, `API_HASH`, connection string com senha, chave
privada FTPS, sessão Telegram ou backups SQL.

## Documentação

- [Instalação no Windows VPS](docs/INSTALLATION.md)
- [Arquitetura e recuperação](docs/ARCHITECTURE.md)
- [Segurança e dados sensíveis](docs/SECURITY.md)
- [Publicação no GitHub](docs/GITHUB.md)
- [Créditos e origem](NOTICE.md)

## Créditos e licença

Esta vertente é mantida por Jefferson e deriva de
[`jeffbart/NebulaFTP`](https://github.com/jeffbart/NebulaFTP). O projeto
NebulaFTP original é creditado a Samuel de Sousa Santos e a licença preservada
atribui copyright a RuslanUC. Consulte [NOTICE.md](NOTICE.md) e
[LICENSE](LICENSE).
