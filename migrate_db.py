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

    engine = create_async_engine(DATABASE_URL, connect_args={"statement_cache_size": 0})
    
    async with engine.connect() as conn:
        print("Running migrations...")
        
        async def run_step(sql, msg):
            try:
                async with conn.begin():
                    await conn.execute(text(sql))
                    print(f"DONE: {msg}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"SKIPPED (Existing): {msg}")
                else:
                    print(f"FAILED: {msg} -> {e}")

        # 1. Base Table
        await run_step("""
            CREATE TABLE IF NOT EXISTS gym_owners (
                id SERIAL PRIMARY KEY,
                gym_name VARCHAR,
                email VARCHAR UNIQUE,
                mobile VARCHAR UNIQUE,
                password VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, "gym_owners table")

        # 2. Member Columns
        await run_step("ALTER TABLE registered_faces ADD COLUMN owner_id INTEGER REFERENCES gym_owners(id)", "owner_id in registered_faces")
        await run_step("ALTER TABLE registered_faces ADD COLUMN subscription_expiry TIMESTAMP", "subscription_expiry in registered_faces")
        await run_step("ALTER TABLE registered_faces ADD COLUMN plan_type VARCHAR DEFAULT 'monthly'", "plan_type in registered_faces")

        # 3. Attendance Columns
        await run_step("ALTER TABLE attendance_logs ADD COLUMN owner_id INTEGER REFERENCES gym_owners(id)", "owner_id in attendance_logs")

        # 4. Settings Columns
        await run_step("ALTER TABLE gym_owners ADD COLUMN webhook_url VARCHAR", "webhook_url in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN notify_on_entry BOOLEAN DEFAULT TRUE", "notify_on_entry in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN notify_on_expiry BOOLEAN DEFAULT TRUE", "notify_on_expiry in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN whatsapp_enabled BOOLEAN DEFAULT FALSE", "whatsapp_enabled in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN whatsapp_number VARCHAR", "whatsapp_number in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN whatsapp_api_key VARCHAR", "whatsapp_api_key in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN whatsapp_provider VARCHAR DEFAULT 'callmebot'", "whatsapp_provider in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN telegram_enabled BOOLEAN DEFAULT FALSE", "telegram_enabled in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN telegram_token VARCHAR", "telegram_token in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN telegram_chat_id VARCHAR", "telegram_chat_id in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN gmail_enabled BOOLEAN DEFAULT FALSE", "gmail_enabled in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN alert_email VARCHAR", "alert_email in gym_owners")
        await run_step("ALTER TABLE gym_owners ADD COLUMN last_ip VARCHAR", "last_ip in gym_owners")
        
        # New Workout Table
        await run_step("""
            CREATE TABLE IF NOT EXISTS workout_sessions (
                id SERIAL PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                exercise_name VARCHAR NOT NULL,
                reps INTEGER DEFAULT 0,
                sets INTEGER DEFAULT 0,
                avg_accuracy INTEGER DEFAULT 0,
                notes VARCHAR,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, "workout_sessions table")

    print("Migration complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
