"""Alternative full Linux VM entry point; shares the verified worker protocol."""
import asyncio
from desktop_worker import main

if __name__ == "__main__":
    asyncio.run(main(runtime="vm"))
