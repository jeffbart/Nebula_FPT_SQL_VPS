# Scripts SQL Server

Estes scripts foram reconstruídos a partir do schema do backup
`VPS_Nebula_20260727_1845.bak`. Nenhuma linha de dados do backup foi incluída.

## Uso no SSMS

1. Abra o SQL Server Management Studio como administrador.
2. Ative **Query > SQLCMD Mode**.
3. Abra `install_all.sql`.
4. Ajuste `DatabaseName` e `ServicePrincipal` no início do arquivo.
5. Execute o script completo.

Exemplo de principal Windows:

```text
NOME-DA-VPS\NebulaFTPSvc
```

Os scripts são idempotentes: podem ser executados novamente sem recriar objetos
existentes. Eles criam somente schema, tabelas, constraints, índices, role e
permissões. Usuários FTP, hashes, catálogo, partes do Telegram, jobs e histórico
não são incluídos.

## Ordem manual

1. `00_create_database.sql` conectado em `master`;
2. `01_create_schema_and_tables.sql` no banco criado;
3. `02_create_indexes.sql`;
4. `03_create_runtime_role.sql`.

Ao executar arquivos individuais com `sqlcmd`, informe as variáveis:

```powershell
sqlcmd -S localhost -E -C -b `
  -v DatabaseName="NebulaFTP" ServicePrincipal="VPS\NebulaFTPSvc" `
  -i .\00_create_database.sql
```
