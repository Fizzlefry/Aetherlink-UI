import importlib
import os
import py_compile


# Files to compile (relative to repository root)
files = [
    "pods/customer-ops/api/deps.py",
    "pods/customer-ops/api/main.py",
    "pods/customer-ops/api/crud.py",
    "pods/customer-ops/api/session.py",
    "pods/customer-ops/api/models.py",
]

print("Running smoke tests: checking imports and syntax")

# Quick import checks for critical packages
packages = ["fastapi", "pydantic", "sqlalchemy"]
for pkg in packages:
    try:
        importlib.import_module(pkg)
        print(f"OK: {pkg} is importable")
    except Exception as e:
        print(f"MISSING: {pkg} -> {e}")

# Compile files
for f in files:
    path = os.path.join(os.getcwd(), f)
    try:
        py_compile.compile(path, doraise=True)
        print(f"COMPILE OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"COMPILE FAIL: {f} -> {e}")
    except FileNotFoundError:
        print(f"MISSING FILE: {f}")

print("Smoke test complete")
