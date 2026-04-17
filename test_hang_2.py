import sys
print("1", flush=True)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
print("2", flush=True)
from sqlalchemy.orm import sessionmaker, declarative_base
print("3", flush=True)
import os
from dotenv import load_dotenv
print("4", flush=True)
load_dotenv()
print("5", flush=True)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./faces.db")
Base = declarative_base()
print("6", flush=True)
try:
    engine = create_async_engine(DATABASE_URL, echo=False)
except Exception as e:
    print(e)
print("7")
