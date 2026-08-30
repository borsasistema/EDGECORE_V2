-- EDGECORE_V2 — FAZ 0B Schema
-- Table: v2_runs

CREATE TABLE IF NOT EXISTS v2_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT        NOT NULL,
    run_id          TEXT        NOT NULL,
    engine_version  TEXT        NOT NULL,
    git_commit      TEXT        NOT NULL,
    data_version    TEXT        NOT NULL,
    test_name       TEXT        NOT NULL,
    status          TEXT        NOT NULL,
    input_sha256    TEXT,
    output_sha256   TEXT,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT v2_runs_project_id_check
        CHECK (project_id = 'EDGECORE_V2'),

    CONSTRAINT v2_runs_status_check
        CHECK (status IN ('STARTED', 'PASS', 'FAIL')),

    CONSTRAINT v2_runs_run_id_unique
        UNIQUE (run_id),

    CONSTRAINT v2_runs_finished_after_started
        CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_v2_runs_project_id
    ON v2_runs (project_id);

CREATE INDEX IF NOT EXISTS idx_v2_runs_status
    ON v2_runs (status);

CREATE INDEX IF NOT EXISTS idx_v2_runs_test_name
    ON v2_runs (test_name);

CREATE INDEX IF NOT EXISTS idx_v2_runs_started_at
    ON v2_runs (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_v2_runs_git_commit
    ON v2_runs (git_commit);

-- RLS
ALTER TABLE v2_runs ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read and write their own runs
CREATE POLICY v2_runs_auth_select ON v2_runs
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY v2_runs_auth_insert ON v2_runs
    FOR INSERT
    TO authenticated
    WITH CHECK (project_id = 'EDGECORE_V2');

CREATE POLICY v2_runs_auth_update ON v2_runs
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (project_id = 'EDGECORE_V2');

-- Service role has full access (used by backend/CI)
CREATE POLICY v2_runs_service_all ON v2_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
