import asyncio
import bcrypt
from database import AsyncSessionLocal
from models import GymOwner
from sqlalchemy.future import select

async def migrate_passwords():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GymOwner))
        owners = result.scalars().all()
        
        updated_count = 0
        for owner in owners:
            # Check if password is already hashed (bcrypt hashes start with $2b$ or $2a$)
            if not owner.password.startswith("$2b$") and not owner.password.startswith("$2a$"):
                print(f"Hashing password for: {owner.email}...")
                hashed = bcrypt.hashpw(owner.password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
                owner.password = hashed
                updated_count += 1
        
        if updated_count > 0:
            await session.commit()
            print(f"✅ Successfully migrated {updated_count} passwords to bcrypt.")
        else:
            print("No plaintext passwords found.")

if __name__ == "__main__":
    asyncio.run(migrate_passwords())
