-- Dead Letter Queue table for failed event persistence
-- Captures events that could not be persisted to event_journal

CREATE TABLE IF NOT EXISTS event_dlq (
    id          SERIAL PRIMARY KEY,
    topic       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    error       TEXT NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for querying recent DLQ entries
CREATE INDEX IF NOT EXISTS idx_event_dlq_received_at ON event_dlq(received_at DESC);

-- Index for filtering by topic
CREATE INDEX IF NOT EXISTS idx_event_dlq_topic ON event_dlq(topic);

COMMENT ON TABLE event_dlq IS 'Dead letter queue for events that failed to persist to event_journal';
COMMENT ON COLUMN event_dlq.topic IS 'Original Kafka topic of the failed event';
COMMENT ON COLUMN event_dlq.payload IS 'Full event payload as JSONB';
COMMENT ON COLUMN event_dlq.error IS 'Error message explaining why persistence failed';
COMMENT ON COLUMN event_dlq.received_at IS 'Timestamp when the event was moved to DLQ';
