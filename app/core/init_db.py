import asyncio
from sqlalchemy import text
from app.core.database import engine, Base
from app.models.embedding import DocumentEmbedding

async def init_tables():
    print("Creating database tables...")
    async with engine.begin() as conn:
        # Create pgvector extension if not exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Create all tables using metadata
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_tables())