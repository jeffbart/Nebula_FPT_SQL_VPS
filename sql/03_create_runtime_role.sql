USE [master];
GO

IF SUSER_ID(N'$(ServicePrincipal)') IS NULL
BEGIN
    DECLARE @createLogin nvarchar(max) =
        N'CREATE LOGIN ' + QUOTENAME(N'$(ServicePrincipal)') + N' FROM WINDOWS;';
    EXEC sys.sp_executesql @createLogin;
END;
GO

USE [$(DatabaseName)];
GO

IF USER_ID(N'$(ServicePrincipal)') IS NULL
BEGIN
    DECLARE @createUser nvarchar(max) =
        N'CREATE USER ' + QUOTENAME(N'$(ServicePrincipal)') +
        N' FOR LOGIN ' + QUOTENAME(N'$(ServicePrincipal)') + N';';
    EXEC sys.sp_executesql @createUser;
END;
GO

IF DATABASE_PRINCIPAL_ID(N'nebula_runtime') IS NULL
    CREATE ROLE nebula_runtime AUTHORIZATION dbo;
GO

GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::nebula TO nebula_runtime;
GRANT EXECUTE ON SCHEMA::nebula TO nebula_runtime;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.database_role_members drm
    WHERE drm.role_principal_id = DATABASE_PRINCIPAL_ID(N'nebula_runtime')
      AND drm.member_principal_id = DATABASE_PRINCIPAL_ID(N'$(ServicePrincipal)')
)
BEGIN
    DECLARE @addMember nvarchar(max) =
        N'ALTER ROLE [nebula_runtime] ADD MEMBER ' +
        QUOTENAME(N'$(ServicePrincipal)') + N';';
    EXEC sys.sp_executesql @addMember;
END;
GO
