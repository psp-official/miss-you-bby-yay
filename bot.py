"""Compatibility entrypoint. The application lives in app.py to avoid duplicate bot logic."""
from app import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
