import asyncio
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if "postgres" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

connect_args = {"statement_cache_size": 0}

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
from models import RegisteredFace

async def clean_db():
    async with AsyncSessionLocal() as session:
        # Delete all faces that start with 'Visitor_'
        result = await session.execute(delete(RegisteredFace).where(RegisteredFace.name.like('Visitor_%')))
        await session.commit()
        print(f"Deleted {result.rowcount} old Visitor profiles to prevent conflicts.")

asyncio.run(clean_db())
