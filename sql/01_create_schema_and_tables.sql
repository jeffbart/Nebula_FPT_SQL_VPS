USE [$(DatabaseName)];
GO
SET XACT_ABORT ON;
GO

IF SCHEMA_ID(N'nebula') IS NULL
    EXEC(N'CREATE SCHEMA [nebula] AUTHORIZATION [dbo]');
GO

IF OBJECT_ID(N'nebula.schema_migrations', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.schema_migrations (
        version int NOT NULL CONSTRAINT PK_schema_migrations PRIMARY KEY,
        name nvarchar(255) NOT NULL,
        applied_at datetime2(3) NOT NULL
            CONSTRAINT DF_schema_migrations_applied_at DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'nebula.users', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.users (
        user_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_users PRIMARY KEY,
        login nvarchar(64) NOT NULL,
        password_hash varchar(255) NOT NULL,
        password_algorithm varchar(20) NOT NULL,
        enabled bit NOT NULL CONSTRAINT DF_users_enabled DEFAULT (1),
        created_at datetime2(3) NOT NULL CONSTRAINT DF_users_created_at DEFAULT SYSUTCDATETIME(),
        updated_at datetime2(3) NOT NULL CONSTRAINT DF_users_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_users_login UNIQUE (login),
        CONSTRAINT CK_users_password_algorithm CHECK (password_algorithm IN ('bcrypt', 'pbkdf2'))
    );
END;
GO

IF OBJECT_ID(N'nebula.permissions', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.permissions (
        permission_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_permissions PRIMARY KEY,
        user_id bigint NOT NULL,
        virtual_path nvarchar(1024) NOT NULL,
        readable bit NOT NULL CONSTRAINT DF_permissions_readable DEFAULT (0),
        writable bit NOT NULL CONSTRAINT DF_permissions_writable DEFAULT (0),
        CONSTRAINT FK_permissions_users FOREIGN KEY (user_id)
            REFERENCES nebula.users(user_id) ON DELETE CASCADE,
        CONSTRAINT UQ_permissions_user_path UNIQUE (user_id, virtual_path)
    );
END;
GO

IF OBJECT_ID(N'nebula.nodes', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.nodes (
        node_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_nodes PRIMARY KEY,
        node_type varchar(10) NOT NULL,
        name nvarchar(255) NOT NULL,
        parent_path nvarchar(1024) NOT NULL,
        size_bytes bigint NOT NULL CONSTRAINT DF_nodes_size DEFAULT (0),
        status varchar(20) NOT NULL CONSTRAINT DF_nodes_status DEFAULT ('completed'),
        local_path nvarchar(2048) NULL,
        obfuscated_id uniqueidentifier NULL,
        created_at datetime2(3) NOT NULL CONSTRAINT DF_nodes_created_at DEFAULT SYSUTCDATETIME(),
        modified_at datetime2(3) NOT NULL CONSTRAINT DF_nodes_modified_at DEFAULT SYSUTCDATETIME(),
        uploaded_at datetime2(3) NULL,
        row_version rowversion NOT NULL,
        CONSTRAINT UQ_nodes_parent_name UNIQUE (parent_path, name),
        CONSTRAINT CK_nodes_type CHECK (node_type IN ('file', 'dir')),
        CONSTRAINT CK_nodes_status CHECK (status IN ('staging', 'uploading', 'completed', 'failed', 'deleting'))
    );
END;
GO

IF OBJECT_ID(N'nebula.file_parts', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.file_parts (
        part_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_file_parts PRIMARY KEY,
        node_id bigint NOT NULL,
        part_number int NOT NULL,
        telegram_file_id nvarchar(512) NOT NULL,
        telegram_message_id bigint NOT NULL,
        telegram_chat_id bigint NOT NULL,
        size_bytes bigint NOT NULL,
        chunk_name nvarchar(255) NOT NULL,
        created_at datetime2(3) NOT NULL CONSTRAINT DF_file_parts_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_file_parts_nodes FOREIGN KEY (node_id)
            REFERENCES nebula.nodes(node_id) ON DELETE CASCADE,
        CONSTRAINT UQ_file_parts_node_number UNIQUE (node_id, part_number)
    );
END;
GO

IF OBJECT_ID(N'nebula.jobs', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.jobs (
        job_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_jobs PRIMARY KEY,
        job_type varchar(20) NOT NULL,
        node_id bigint NULL,
        status varchar(20) NOT NULL CONSTRAINT DF_jobs_status DEFAULT ('pending'),
        attempts int NOT NULL CONSTRAINT DF_jobs_attempts DEFAULT (0),
        available_at datetime2(3) NOT NULL CONSTRAINT DF_jobs_available_at DEFAULT SYSUTCDATETIME(),
        locked_at datetime2(3) NULL,
        locked_by nvarchar(128) NULL,
        last_error nvarchar(4000) NULL,
        created_at datetime2(3) NOT NULL CONSTRAINT DF_jobs_created_at DEFAULT SYSUTCDATETIME(),
        updated_at datetime2(3) NOT NULL CONSTRAINT DF_jobs_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_jobs_nodes FOREIGN KEY (node_id)
            REFERENCES nebula.nodes(node_id) ON DELETE CASCADE,
        CONSTRAINT CK_jobs_type CHECK (job_type IN ('upload', 'delete')),
        CONSTRAINT CK_jobs_status CHECK (status IN ('pending', 'running', 'completed', 'failed'))
    );
END;
GO

IF OBJECT_ID(N'nebula.operation_history', N'U') IS NULL
BEGIN
    CREATE TABLE nebula.operation_history (
        history_id bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_operation_history PRIMARY KEY,
        operation varchar(30) NOT NULL,
        actor nvarchar(128) NULL,
        virtual_path nvarchar(1024) NULL,
        node_id bigint NULL,
        success bit NOT NULL,
        details nvarchar(4000) NULL,
        occurred_at datetime2(3) NOT NULL CONSTRAINT DF_operation_history_time DEFAULT SYSUTCDATETIME()
    );
END;
GO
