from src import tasks
from src.services.worker import app


@app.periodic(cron='0 */2 * * *')
@app.task(queueing_lock='poll_all_feeds')
async def poll_all_feeds(timestamp: int) -> None:
    for category in ('Python',):
        await tasks.process_feed.defer_async(category=category)


@app.periodic(cron='5 */4 * * *')
@app.task(queueing_lock='enqueue_vacancies')
async def enqueue_vacancies_cron(timestamp: int) -> None:
    await tasks.enqueue_vacancies()
