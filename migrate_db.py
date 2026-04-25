import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

async def migrate():
    if not DATABASE_URL:
        print("DATABASE_URL not found.")
        return

    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Running migrations...")
        
        # Create gym_owners table if not exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gym_owners (
                id SERIAL PRIMARY KEY,
                gym_name VARCHAR,
                email VARCHAR UNIQUE,
                mobile VARCHAR UNIQUE,
                password_hash VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Add columns to registered_faces
        try:
            await conn.execute(text("ALTER TABLE registered_faces ADD COLUMN owner_id INTEGER REFERENCES gym_owners(id)"))
            print("Added owner_id to registered_faces")
        except Exception as e:
            print(f"Skipped owner_id in registered_faces: {e}")

        try:
            await conn.execute(text("ALTER TABLE registered_faces ADD COLUMN subscription_expiry TIMESTAMP"))
            print("Added subscription_expiry to registered_faces")
        except Exception as e:
            print(f"Skipped subscription_expiry in registered_faces: {e}")

        try:
            await conn.execute(text("ALTER TABLE registered_faces ADD COLUMN plan_type VARCHAR DEFAULT 'monthly'"))
            print("Added plan_type to registered_faces")
        except Exception as e:
            print(f"Skipped plan_type in registered_faces: {e}")

        # Add columns to attendance_logs
        try:
            await conn.execute(text("ALTER TABLE attendance_logs ADD COLUMN owner_id INTEGER REFERENCES gym_owners(id)"))
            print("Added owner_id to attendance_logs")
        except Exception as e:
            print(f"Skipped owner_id in attendance_logs: {e}")

    print("Migration complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
