USE [$(DatabaseName)];
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'nebula.nodes')
      AND name = N'IX_nodes_parent_type'
)
BEGIN
    CREATE INDEX IX_nodes_parent_type
        ON nebula.nodes(parent_path, node_type)
        INCLUDE (name, size_bytes, modified_at, status);
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'nebula.jobs')
      AND name = N'IX_jobs_claim'
)
BEGIN
    CREATE INDEX IX_jobs_claim
        ON nebula.jobs(status, available_at, job_type)
        INCLUDE (node_id, attempts);
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'nebula.operation_history')
      AND name = N'IX_operation_history_time'
)
BEGIN
    CREATE INDEX IX_operation_history_time
        ON nebula.operation_history(occurred_at DESC);
END;
GO
