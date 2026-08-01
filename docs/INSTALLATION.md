# Instalação no Windows VPS

## Requisitos

- Windows Server ou Windows 10/11 x64;
- Python 3.11 x64;
- Microsoft SQL Server;
- SQL Server Management Studio (SSMS);
- ODBC Driver 18 for SQL Server;
- PowerShell 5.1 ou superior;
- bot e canal privado do Telegram;
- certificado e chave FTPS.

## 1. Preparar o ambiente Python

Na raiz do projeto:

```powershell
py -3.11 -m venv .\venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r .\app\requirements.txt
```

## 2. Criar a conta de serviço do Windows

Abra o PowerShell como Administrador:

```powershell
$servicePassword = Read-Host "Senha da conta de serviço" -AsSecureString

New-LocalUser `
  -Name "NebulaFTPSvc" `
  -Password $servicePassword `
  -AccountNeverExpires `
  -PasswordNeverExpires `
  -UserMayNotChangePassword `
  -Description "Conta de serviço do NebulaFTP"
```

O principal usado no SQL Server será semelhante a:

```text
NOME-DA-VPS\NebulaFTPSvc
```

Descubra o nome correto do computador com:

```powershell
$env:COMPUTERNAME
```

## 3. Criar o banco e as tabelas pelo SSMS

Esta é a opção recomendada para uma instalação nova.

1. Abra o SQL Server Management Studio com uma conta administradora.
2. Conecte-se à instância local do SQL Server.
3. No menu do SSMS, ative **Query > SQLCMD Mode**.
4. Abra `sql\install_all.sql` a partir da pasta do projeto.
5. Ajuste as duas variáveis no início do arquivo:

```sql
:setvar DatabaseName "NebulaFTP"
:setvar ServicePrincipal "NOME-DA-VPS\NebulaFTPSvc"
```

6. Execute o script completo.

O instalador chama, nesta ordem:

- `00_create_database.sql`: cria e configura o banco;
- `01_create_schema_and_tables.sql`: cria o schema e as sete tabelas;
- `02_create_indexes.sql`: cria os índices de catálogo, jobs e histórico;
- `03_create_runtime_role.sql`: cria login, usuário, role e permissões.

Os scripts são idempotentes e não inserem usuários FTP, senhas, catálogo ou
dados do Telegram.

### Validar a instalação no SSMS

Execute:

```sql
USE [NebulaFTP];
GO

SELECT
    s.name AS schema_name,
    t.name AS table_name
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'nebula'
ORDER BY t.name;

SELECT name, type_desc
FROM sys.database_principals
WHERE name = N'nebula_runtime';
```

Devem aparecer sete tabelas:

```text
file_parts
jobs
nodes
operation_history
permissions
schema_migrations
users
```

Também deve aparecer a role `nebula_runtime`.

### Alternativa por linha de comando

Edite primeiro `sql\install_all.sql` e execute a partir da pasta `sql`:

```powershell
Set-Location .\sql
sqlcmd -S localhost -E -C -b -i .\install_all.sql
Set-Location ..
```

### Alternativa pelas migrations Python

Use esta opção somente quando o banco `NebulaFTP` já existir e a conta que
executa o comando tiver permissão para criar o schema e as tabelas:

```powershell
$env:NEBULA_ENV_FILE = "$PWD\config\.env"
.\venv\Scripts\python.exe .\app\scripts\migrate.py
```

Para SQL Server local, prefira `Trusted_Connection=yes`. Não exponha a porta
1433 à internet.

## 4. Configurar o ambiente

Copie o modelo:

```powershell
Copy-Item .\config\.env.vps.example .\config\.env
```

Preencha:

- `API_ID`;
- `API_HASH`;
- `BOT_TOKEN`;
- `CHAT_ID`;
- `PASSIVE_HOST` e `PASSIVE_PORTS`;
- caminhos do certificado, staging, dados e logs;
- `NEBULA_DB_CONNECTION`.

Exemplo para SQL Server local:

```dotenv
NEBULA_DB_CONNECTION=DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=NebulaFTP;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;
```

O arquivo `config\.env` contém segredos e não deve ser enviado ao GitHub.

## 5. Gerar o certificado FTPS

Para laboratório:

```powershell
.\venv\Scripts\python.exe .\app\scripts\generate_test_certificate.py `
  --host SEU_IP_OU_DOMINIO `
  --output .\certs
```

Use certificado confiável em produção. A chave privada não deve entrar no Git.

## 6. Criar usuário FTP

```powershell
$env:NEBULA_ENV_FILE = "$PWD\config\.env"
.\venv\Scripts\python.exe .\app\accounts_manager.py add usuario
```

As senhas são armazenadas como hashes bcrypt.

## 7. Configurar o firewall

Exemplo para porta de controle 2121 e faixa passiva 60000–60049:

```powershell
New-NetFirewallRule `
  -DisplayName "NebulaFTP FTPS Control" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 2121 `
  -Action Allow

New-NetFirewallRule `
  -DisplayName "NebulaFTP FTPS Passive" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 60000-60049 `
  -Action Allow
```

Não libere a porta 1433 do SQL Server para a internet.

## 8. Iniciar o NebulaFTP

Execute na raiz:

```powershell
.\iniciar_nebulaftp_vps.bat
```

No WinSCP:

- protocolo: FTP;
- criptografia: TLS/SSL explícita;
- modo: passivo;
- porta: a definida em `PORT`;
- usuário: criado pelo gerenciador de contas.

## 9. Executar os testes

```powershell
$env:PYTHONPATH = "$PWD\app"
.\venv\Scripts\python.exe -m unittest discover -s .\app\tests -v
```
