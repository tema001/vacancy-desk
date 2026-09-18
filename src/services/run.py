import asyncio
import importlib
import logging
import sys

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)

if __name__ == '__main__':
    name = sys.argv[1]
    mod = importlib.import_module(f'src.services.{name}')
    asyncio.run(mod.run())
