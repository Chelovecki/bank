from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="docker/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    # Postgres settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_DB: str = "bank"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_PORT: int = 5432
    POSTGRES_DATABASE_URL: Optional[str] = None

    # Bank API settings
    BANK_API_BASE_URL: str = "https://bank.api"
    BANK_API_TIMEOUT_SECONDS: float = 5
    BANK_API_RETRIES: int = 2

    @computed_field
    @property
    def ASYNC_URL(self) -> str:
        """Генерирует URL для подключения к БД"""
        if self.POSTGRES_DATABASE_URL:
            return self.POSTGRES_DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def get_db_session(self):
        """Создает фабрику сессий для БД"""
        engine = create_async_engine(
            self.ASYNC_URL,
            echo=False,
            pool_size=20,
            max_overflow=40,
        )
        return async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )


settings = Settings()
