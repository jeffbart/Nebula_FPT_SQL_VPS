USE [master];
GO

IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    DECLARE @createDatabase nvarchar(max) =
        N'CREATE DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N';';
    EXEC sys.sp_executesql @createDatabase;
END;
GO

DECLARE @configureDatabase nvarchar(max) = N'
ALTER DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N' SET RECOVERY SIMPLE;
ALTER DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N' SET AUTO_CLOSE OFF;
ALTER DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N' SET AUTO_SHRINK OFF;
ALTER DATABASE ' + QUOTENAME(N'$(DatabaseName)') +
N' SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;';
EXEC sys.sp_executesql @configureDatabase;
GO
