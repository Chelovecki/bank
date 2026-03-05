from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class BaseService:
    def __init__(self, session):
        self.session_factory: async_sessionmaker[AsyncSession] = session