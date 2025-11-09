#!/usr/bin/env python3
import sys
sys.path.insert(0, 'services/command-center')

try:
    from main import app
    print("App imported successfully")
    print(f"App type: {type(app)}")
    print(f"App title: {getattr(app, 'title', 'No title')}")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()