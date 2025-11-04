"""
Fails if Alembic would autogenerate a new revision (i.e., models != DB).
Runs autogen into a temp versions folder so your repo stays clean.
"""
import os, sys, tempfile, shutil, subprocess, textwrap, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
alembic_ini = ROOT / "alembic.ini"
if not alembic_ini.exists():
    print("alembic.ini not found next to repo root", file=sys.stderr)
    sys.exit(2)

# Ensure DATABASE_URL so env.py can run
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink",
)

tmpdir = tempfile.mkdtemp(prefix="alembic_check_")
try:
    # Run: alembic -c alembic.ini revision --autogenerate -m check --version-path <tmp>
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", str(alembic_ini),
        "revision", "--autogenerate",
        "-m", "schema_drift_check",
        "--version-path", tmpdir,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")

    # Alembic prints this when there are NO changes:
    no_changes = "No changes in schema detected." in out

    # If a file appeared in temp versions dir, then autogen found diffs
    generated = any(pathlib.Path(tmpdir).glob("*.py"))

    if no_changes and not generated:
        print("✅ Alembic clean: no schema changes detected.")
        sys.exit(0)

    # Otherwise: fail with a helpful message and show the generated diff header
    print("❌ Alembic found schema changes not captured by a migration.", file=sys.stderr)
    if generated:
        # Show the first few lines of the generated file to hint at changes
        gen = sorted(pathlib.Path(tmpdir).glob("*.py"))[0]
        preview = "\n".join(gen.read_text(encoding="utf-8").splitlines()[:40])
        print("\n--- Generated (preview) ---\n" + preview + "\n---------------------------", file=sys.stderr)

    print(textwrap.dedent("""
        Fix:
          1) Make sure Docker Postgres is running (`./dev_setup.ps1`)
          2) Create a real migration: `./dev_migrate.ps1 -RevMsg "describe change"`
          3) Re-run checks.
    """).strip(), file=sys.stderr)
    sys.exit(1)

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
