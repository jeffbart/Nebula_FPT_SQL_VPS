:setvar DatabaseName "NebulaFTP"
:setvar ServicePrincipal "COMPUTER_NAME\NebulaFTPSvc"

:on error exit

:r .\00_create_database.sql
:r .\01_create_schema_and_tables.sql
:r .\02_create_indexes.sql
:r .\03_create_runtime_role.sql

PRINT N'NebulaFTP SQL Server instalado com sucesso.';
GO
