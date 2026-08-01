# Instalação no Windows VPS

## Requisitos

- Windows Server ou Windows 10/11 x64;
- Python 3.11 x64;
- Microsoft SQL Server;
- ODBC Driver 18 for SQL Server;
- PowerShell 5.1+;
- bot e canal privado do Telegram;
- certificado e chave FTPS.

## 1. Preparar o ambiente

Na raiz do projeto:

```powershell
py -3.11 -m venv .\venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r .\app\requirements.txt
```

## 2. Configurar o SQL Server

Crie o banco `NebulaFTP`, o schema `nebula` e aplique as migrations:

```powershell
$env:NEBULA_ENV_FILE = "$PWD\config\.env"
.\venv\Scripts\python.exe .\app\scripts\migrate.py
```

Use a connection string configurada em `NEBULA_DB_CONNECTION`. Para uma VPS
com SQL local, prefira `Trusted_Connection=yes` e não abra a porta 1433.

## 3. Configuração

```powershell
Copy-Item .\config\.env.vps.example .\config\.env
```

Preencha `API_ID`, `API_HASH`, `BOT_TOKEN`, `CHAT_ID`, caminhos do certificado,
staging, dados, logs, portas passivas e conexão SQL.

## 4. Certificado

Para laboratório:

```powershell
.\venv\Scripts\python.exe .\app\scripts\generate_test_certificate.py `
  --host SEU_IP_OU_DOMINIO --output .\certs
```

Use certificado confiável em produção.

## 5. Usuário FTP

```powershell
$env:NEBULA_ENV_FILE = "$PWD\config\.env"
.\venv\Scripts\python.exe .\app\accounts_manager.py add usuario
```

## 6. Iniciar

Execute na raiz:

```powershell
.\iniciar_nebulaftp_vps.bat
```

No WinSCP, escolha FTP com TLS/SSL explícita e modo passivo. Use a porta de
controle configurada e libere também a faixa `PASSIVE_PORTS` no firewall.

## 7. Testes

```powershell
$env:PYTHONPATH = "$PWD\app"
.\venv\Scripts\python.exe -m unittest discover -s .\app\tests -v
```
