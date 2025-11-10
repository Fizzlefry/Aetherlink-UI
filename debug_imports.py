import os
import sys
from pathlib import Path

# Mimic the run-command-center.ps1 setup
repo = r"C:\Users\jonmi\OneDrive\Documents\AetherLink"
os.chdir(repo)
sys.path.insert(0, repo)
sys.path.insert(0, os.path.join(repo, "services", "command-center"))

# Now try the imports
try:
    from services.command_center.persistence.json_fallback import JSONBackend
    from services.command_center.persistence.sqlite import SQLiteBackend

    print("Imports successful")
except ImportError as e:
    print(f"Import failed: {e}")

# Try relative import
try:
    os.chdir(os.path.join(repo, "services", "command-center"))
    from persistence.json_fallback import JSONBackend
    from persistence.sqlite import SQLiteBackend

    print("Relative imports successful")
except ImportError as e:
    print(f"Relative import failed: {e}")

# Check paths
ROOT = Path(__file__).resolve().parent
print(f"ROOT: {ROOT}")
DATA_DIR = ROOT / "data"
print(f"DATA_DIR: {DATA_DIR}")
STORE_DSN = str(DATA_DIR / "command_center.db")
print(f"STORE_DSN: {STORE_DSN}")

# Try creating backend
try:
    backend = SQLiteBackend(db_path=STORE_DSN)
    print("Backend created successfully")
except Exception as e:
    print(f"Backend creation failed: {e}")
    import traceback

    traceback.print_exc()
