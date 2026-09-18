import asyncio
from collections.abc import Awaitable
from typing import Any

import procrastinate
from procrastinate.job_context import JobContext
from procrastinate.worker import Worker

from src.shared.resources import resources

resources.load_config()
config = resources.config


async def job_timeout(call_next, context: JobContext, worker: Worker) -> Awaitable[Any]:
    async with asyncio.timeout(30):
        return await call_next()


app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=config['db']['dsn']),
    import_paths=['src.tasks', 'src.cron'],
    worker_defaults={
        'concurrency': 3,
        'shutdown_graceful_timeout': 2.0,
        'delete_jobs': 'successful',
        'worker_middleware': [job_timeout],
    },
)


async def run() -> None:
    await resources.start(start_llm=True)
    try:
        async with app.open_async():
            await app.run_worker_async()
    finally:
        await resources.stop()
