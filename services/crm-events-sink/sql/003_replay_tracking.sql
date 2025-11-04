-- Add replay tracking to event_journal
-- Allows distinguishing original events from replayed events in analytics

ALTER TABLE event_journal
ADD COLUMN replay_count INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN replay_source TEXT DEFAULT NULL;

-- Index for filtering replayed vs original events
CREATE INDEX IF NOT EXISTS idx_event_journal_replay_count ON event_journal(replay_count);

-- Comments
COMMENT ON COLUMN event_journal.replay_count IS 'Number of times this event has been replayed (0 = original)';
COMMENT ON COLUMN event_journal.replay_source IS 'Source of replay: "operator_api", "automated", etc.';

-- Example queries after this migration:

-- Count original vs replayed events
-- SELECT
--   CASE WHEN replay_count = 0 THEN 'original' ELSE 'replayed' END AS event_type,
--   COUNT(*)
-- FROM event_journal
-- GROUP BY event_type;

-- Find all replayed events
-- SELECT id, topic, tenant_id, replay_count, replay_source, received_at
-- FROM event_journal
-- WHERE replay_count > 0
-- ORDER BY received_at DESC;
