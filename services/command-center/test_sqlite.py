import asyncio
import sys

sys.path.insert(0, ".")

from persistence.sqlite import SQLiteBackend


async def test():
    backend = SQLiteBackend("data/command_center.db")
    try:
        await backend.initialize()
        print("SQLite backend initialized successfully")
        await backend.close()
    except Exception as e:
        print(f"Failed to initialize: {e}")
        import traceback

        traceback.print_exc()


asyncio.run(test())
