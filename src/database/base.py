from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..config import settings
from .models import Base


engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)
async_session_factory = AsyncSessionLocal


async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session