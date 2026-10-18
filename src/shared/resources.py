from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import httpx2
from envyaml import EnvYAML
from langfuse import Langfuse
from langfuse.model import PromptClient
from langfuse.openai import AsyncOpenAI
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio.engine import create_async_engine

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from psycopg_pool import AsyncConnectionPool

    AgentGraph = CompiledStateGraph[Any, Any, Any, Any]


class Resources:
    def __init__(self) -> None:
        self._client: httpx2.AsyncClient | None = None
        self._engine: AsyncEngine | None = None
        self._config: Mapping[str, Any] | None = None
        self._llm: AsyncOpenAI | None = None
        self._langfuse: Langfuse | None = None
        self._pool: AsyncConnectionPool[Any] | None = None
        self._agent: AgentGraph | None = None

    def set_client(self, client: httpx2.AsyncClient) -> None:
        self._client = client

    def set_engine(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def set_config(self, config: Mapping[str, Any]) -> None:
        self._config = config

    def set_llm(self, llm: AsyncOpenAI) -> None:
        self._llm = llm

    def set_langfuse(self, langfuse: Langfuse) -> None:
        self._langfuse = langfuse

    @property
    def client(self) -> httpx2.AsyncClient:
        if self._client is None:
            raise RuntimeError('http client is not started')
        return self._client

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError('db engine is not started')
        return self._engine

    @property
    def config(self) -> Mapping[str, Any]:
        if self._config is None:
            raise RuntimeError('config is not loaded')
        return self._config

    @property
    def llm(self) -> AsyncOpenAI:
        if self._llm is None:
            raise RuntimeError('llm client is not started')
        return self._llm

    @property
    def langfuse(self) -> Langfuse:
        if self._langfuse is None:
            raise RuntimeError('langfuse client is not started')
        return self._langfuse

    @property
    def agent(self) -> AgentGraph:
        if self._agent is None:
            raise RuntimeError('agent is not started')
        return self._agent

    def load_config(self) -> None:
        if self._config is None:
            self.set_config(EnvYAML('config/config.yaml'))

    def get_prompt(self, name: str) -> PromptClient:
        label = self.config['llm']['prompt_label']

        return self.langfuse.get_prompt(name, type='chat', label=label)

    async def start(
        self,
        start_llm: bool = False,
        warmup_llm: bool = False,
        init_agent: bool = False,
    ) -> None:
        self.load_config()

        if self._client is None:
            client = httpx2.AsyncClient(
                timeout=httpx2.Timeout(10.0, connect=5.0),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
                    ' AppleWebKit/537.36 (KHTML, like Gecko)'
                    ' Chrome/151.0.0.0 Safari/537.36'
                },
                follow_redirects=True,
            )
            self.set_client(client)

        db = self.config['db']
        if self._engine is None:
            engine = create_async_engine(
                url=postgres_url(db['dsn'], driver='asyncpg'),
                pool_size=db['pool_size'],
                max_overflow=db['pool_overflow_size'],
                pool_timeout=db['pool_timeout'],
                pool_pre_ping=True,
                connect_args={
                    'server_settings': {'timezone': self.config['app']['time_zone']}
                },
            )
            self.set_engine(engine)

        if start_llm:
            if self._llm is None:
                self.set_llm(AsyncOpenAI(timeout=httpx2.Timeout(30.0, connect=5.0)))

            if self._langfuse is None:
                self.set_langfuse(Langfuse())

            if warmup_llm and self._langfuse:
                # warmup prompts
                names = ('vacancy-extract', 'profile-extract', 'lexicon-expand')
                async with asyncio.TaskGroup() as tg:
                    for name in names:
                        tg.create_task(asyncio.to_thread(self.get_prompt, name))

        if init_agent:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool

            from src.ai_agent.workflow import builder

            pool = AsyncConnectionPool(
                conninfo=db['dsn'],
                kwargs={
                    'autocommit': True,
                    'prepare_threshold': 0,
                    'row_factory': dict_row,
                },
                open=False,
            )
            await pool.open()
            self._pool = pool
            self._agent = builder.compile(checkpointer=AsyncPostgresSaver(pool))

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

        if self._engine:
            await self._engine.dispose()
            self._engine = None

        if self._llm:
            await self._llm.close()
            self._llm = None

        if self._langfuse:
            await asyncio.to_thread(self._langfuse.shutdown)
            self._langfuse = None

        if self._pool:
            await self._pool.close()
            self._pool = None
            self._agent = None


def postgres_url(dsn: str, driver: str | None = None) -> URL:
    name = f'postgresql+{driver}' if driver else 'postgresql'
    return make_url(dsn).set(drivername=name)


resources = Resources()
