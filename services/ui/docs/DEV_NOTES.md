## Commit hooks / known skips

- Some commits may fail pre-commit on:
  - `detect-secrets` → `.secrets.baseline` is not present in this repo
  - `alembic-schema-drift` → the hook reports backend schema drift unrelated to UI

- For UI-only changes (React, docs, etc.) that do not touch backend schemas or secrets, it is acceptable to run:

  ```bash
  SKIP=detect-secrets,alembic-schema-drift git commit -m "your message"
  ```

- Always run the UI build before committing UI changes:

  ```bash
  cd services/ui
  npx vite build
  ```

- If you do add real secrets or touch DB migrations, re-enable the hooks and fix the root cause instead of skipping.
