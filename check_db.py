import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('DATABASE_URL', 'sqlite:///./faces.db').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'gym_owners'"))
    columns = [r[0] for r in res]
    print(f"Columns: {columns}")
