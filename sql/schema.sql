CREATE TABLE IF NOT EXISTS detection_results (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    endpoint_uri VARCHAR(512) NOT NULL,
    response_time_ms DOUBLE PRECISION NOT NULL,
    status_code INTEGER NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_detection_results_predicted_at
ON detection_results (predicted_at DESC);
