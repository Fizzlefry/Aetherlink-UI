# AetherLink Media Service

Simple file upload and media catalog for AetherLink apps. Backed by SQLite and a local `./media` folder in development.

- Base URL: `http://localhost:9109`
- Media root: `./media` (served at `GET /media/{filename}`)
- Database: `./media.db` (override with `MEDIA_DB_PATH`)

## Endpoints

- `POST /upload`
  - Multipart form fields: `file` (required), `job_id` (optional), `tag` (optional)
  - Returns: `media_id`, `url`, `job_id`, `tag`, `uploaded_at`
  - Example:
    ```bash
    curl -F "file=@/path/photo.jpg" -F job_id=123 -F tag=before \
      http://localhost:9109/upload
    ```

- `GET /uploads`
  - Query: `job_id` (optional), `tag` (optional), `limit` (default 50, max 500)
  - Returns: recent uploads (most recent first) with stored metadata
  - Example:
    ```bash
    curl "http://localhost:9109/uploads?job_id=123&tag=before&limit=25"
    ```

- `GET /uploads/stats`
  - Returns aggregate storage and activity statistics for dashboards
  - Response shape (structured + flat for backward compatibility):
    ```json
    {
      "summary": {
        "total_files": 0,
        "total_size_mb": 0.0,
        "uploads_today": 0
      },
      "details": {
        "total_size_bytes": 0,
        "uploads_last_24h": 0,
        "by_mime_type": {},
        "timestamp": "2025-11-07T00:00:00.000000Z"
      },
      "total_files": 0,
      "total_size_bytes": 0,
      "total_size_mb": 0.0,
      "uploads_today": 0,
      "uploads_last_24h": 0,
      "by_mime_type": {},
      "timestamp": "2025-11-07T00:00:00.000000Z"
    }
    ```
  - Notes:
    - New consumers should read from `summary`/`details`.
    - Flat fields are preserved to keep older UIs working.
    - `uploads_today` uses the UTC date prefix of `created_at` (ISO-8601 string).
    - `uploads_last_24h` uses a rolling window based on current UTC time.
    - Backed by indexes on `created_at`, `job_id`, `tag` for efficient queries.

## Data Model

Table `uploads`:

```sql
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  media_id TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  original_filename TEXT,
  url TEXT NOT NULL,
  mime_type TEXT,
  size_bytes INTEGER,
  job_id TEXT,
  tag TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uploads_job_id ON uploads(job_id);
CREATE INDEX IF NOT EXISTS idx_uploads_created ON uploads(created_at);
CREATE INDEX IF NOT EXISTS idx_uploads_tag ON uploads(tag);
```

## Security

- Dev: open locally for rapid iteration.
- Prod: front with the app/API gateway and add token verification between RoofWonder and Media Service.

## Future Enhancements

- Optional nested payload for `/uploads/stats` (`summary` + `details`) to support lightweight badges and rich dashboards without breaking existing consumers.
