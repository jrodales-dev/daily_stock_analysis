from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings

# Convert sync URI to async URI (for asyncpg)
database_url = settings.SQLALCHEMY_DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(database_url, echo=settings.DEBUG)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
