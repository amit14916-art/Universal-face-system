import asyncio
from database import AsyncSessionLocal
from models import GymOwner
from sqlalchemy.future import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GymOwner))
        owners = result.scalars().all()
        for owner in owners:
            print(f"Email: {owner.email} | Mobile: {owner.mobile} | PwdHash: {owner.password}")

if __name__ == "__main__":
    asyncio.run(check())
