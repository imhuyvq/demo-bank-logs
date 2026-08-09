-- PostgreSQL schema for QoS Anomaly Detection module

CREATE TABLE IF NOT EXISTS dataset_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    endpoint_uri VARCHAR(512) NOT NULL,
    http_method VARCHAR(16) NOT NULL,
    response_time_ms DOUBLE PRECISION NOT NULL,
    status_code INTEGER NOT NULL,
    bytes_sent INTEGER NOT NULL,
    is_anomaly INTEGER,
    anomaly_type VARCHAR(32),
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_logs_client_ip ON dataset_logs(client_ip);

CREATE TABLE IF NOT EXISTS detection_results (
    id SERIAL PRIMARY KEY,
    log_id INTEGER NOT NULL REFERENCES dataset_logs(id),
    anomaly_score DOUBLE PRECISION NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    predicted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_detection_results_is_anomaly ON detection_results(is_anomaly);
CREATE INDEX IF NOT EXISTS idx_detection_results_predicted_at ON detection_results(predicted_at);
