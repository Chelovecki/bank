import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv("docker/.env")


class PostgresSettings:
    HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB = os.getenv("POSTGRES_DB")
    USER = os.getenv("POSTGRES_USER")
    PASSWORD = os.getenv("POSTGRES_PASSWORD")
    PORT = int(os.getenv("POSTGRES_PORT"))  # type: ignore
    ASYNC_URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"

    @classmethod
    def get_session(cls):
        async_engine = create_async_engine(
            cls.ASYNC_URL,
            echo=True,
            pool_size=20,
            max_overflow=40,
        )

        return async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
