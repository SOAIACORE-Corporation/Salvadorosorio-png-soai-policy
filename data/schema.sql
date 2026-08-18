PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  source TEXT NOT NULL CHECK (source IN ('whatsapp','telegram','instagram','manual','ocr')),
  conversation_id TEXT,
  sender_ref TEXT,
  received_at TEXT NOT NULL,
  content_type TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  media_ref TEXT,
  sensitivity TEXT NOT NULL CHECK (sensitivity IN ('LOW','MEDIUM','HIGH','RESTRICTED')),
  analysis_status TEXT NOT NULL DEFAULT 'PENDING_ANALYSIS_APPROVAL',
  send_status TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',
  retention_class TEXT NOT NULL CHECK (retention_class IN ('EPHEMERAL','CONTEXTUAL','ARCHIVAL','RESTRICTED')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_source_received ON events(source, received_at);
CREATE INDEX IF NOT EXISTS idx_events_hash ON events(content_hash);
CREATE INDEX IF NOT EXISTS idx_events_analysis ON events(analysis_status);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  gate TEXT NOT NULL CHECK (gate IN ('ANALYSIS','SEND','RETENTION_DELETE')),
  decision TEXT NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata_json TEXT,
  FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS media_manifest (
  content_hash TEXT PRIMARY KEY,
  canonical_ref TEXT,
  size_bytes INTEGER,
  mime_type TEXT,
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  duplicate_count INTEGER NOT NULL DEFAULT 0,
  retention_class TEXT NOT NULL,
  delete_after TEXT
);
