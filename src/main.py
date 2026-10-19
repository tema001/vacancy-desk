from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.routes.chats import router as agent_router
from src.routes.internal import router as internal_router
from src.routes.profiles import router as profiles_router
from src.routes.vacancies import router as vacancies_router
from src.services.worker import app as worker
from src.shared.resources import resources


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await resources.start(start_llm=True, init_agent=True)

    try:
        async with worker.open_async():
            yield
    finally:
        await resources.stop()


app = FastAPI(title='Vacancy Desk', lifespan=lifespan)

app.include_router(profiles_router)
app.include_router(vacancies_router)
app.include_router(internal_router)
app.include_router(agent_router)

DIST = Path(__file__).parent / 'dist'

app.mount('/app/assets', StaticFiles(directory=DIST / 'assets'), name='static')


@app.get('/app', include_in_schema=False)
@app.get('/app/{path:path}', include_in_schema=False)
async def frontend(path: str = '') -> FileResponse:
    return FileResponse(DIST / 'index.html')


@app.get('/', include_in_schema=False)
async def redirect_to_app() -> RedirectResponse:
    return RedirectResponse('/app')
