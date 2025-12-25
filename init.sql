-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- We need to wait for the tables to be created by SQLAlchemy (or migration tool)
-- But for this MVP, since we use `Base.metadata.create_all`, the tables will be created by the app on startup.
-- However, we must convert the `metrics` table to a hypertable AFTER it is created.
-- In a real setup, we'd use Alembic migrations.
-- For this MVP, I will create a function/trigger or just rely on manual conversion?
-- Actually, let's pre-create the metrics table here to ensure it's a hypertable from the start,
-- OR we can let the app create it and then we run a command. 
-- Better approach for MVP: The app creates tables. Then we run a script to convert it.
-- Or, simpler: Just create the metrics table here via SQL.

CREATE TABLE IF NOT EXISTS metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL,
    metric_type TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    meta_data JSONB
);

-- Convert to hypertable
SELECT create_hypertable('metrics', 'time', if_not_exists => TRUE);
