from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./faces.db")
print(f"DEBUG: Initializing database with {'PostgreSQL' if 'postgres' in DATABASE_URL else 'SQLite'}")


Base = declarative_base()

# Configure engine automatically based on environment
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
else:
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
    pool_recycle=60
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    if "postgres" in DATABASE_URL:
        # Initialize pgvector extension safely for Supabase
        import asyncpg
        try:
            raw_url = DATABASE_URL.replace("+asyncpg", "")
            conn = await asyncpg.connect(raw_url)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.close()
        except Exception as e:
            pass
            
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("OK: Securely Connected to Enterprise Database")
    except Exception as e:
        print(f"DATABASE ERROR: {str(e)}")

