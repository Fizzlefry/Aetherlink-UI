-- Event Journal Table for CRM Events Sink
-- Stores all CRM domain events for historical analysis, replay, and audit

CREATE TABLE IF NOT EXISTS event_journal (
    id          SERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    topic       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_event_journal_topic 
    ON event_journal(topic);

CREATE INDEX IF NOT EXISTS idx_event_journal_tenant 
    ON event_journal(tenant_id);

CREATE INDEX IF NOT EXISTS idx_event_journal_received_at 
    ON event_journal(received_at DESC);

-- Composite index for tenant + topic queries
CREATE INDEX IF NOT EXISTS idx_event_journal_tenant_topic 
    ON event_journal(tenant_id, topic);

-- GIN index for JSONB payload searches
CREATE INDEX IF NOT EXISTS idx_event_journal_payload 
    ON event_journal USING GIN (payload);

COMMENT ON TABLE event_journal IS 'Stores all CRM domain events from Kafka for historical analysis and replay';
COMMENT ON COLUMN event_journal.tenant_id IS 'Multi-tenant identifier from event payload';
COMMENT ON COLUMN event_journal.topic IS 'Kafka topic name (e.g., apexflow.leads.created)';
COMMENT ON COLUMN event_journal.payload IS 'Full event payload as JSON';
COMMENT ON COLUMN event_journal.received_at IS 'Timestamp when event was consumed by sink';
