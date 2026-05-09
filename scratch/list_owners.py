import asyncio
from database import AsyncSessionLocal
from models import GymOwner
from sqlalchemy.future import select

async def list_owners():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GymOwner))
        owners = result.scalars().all()
        for owner in owners:
            print(f"ID: {owner.id} | Name: {owner.gym_name} | Email: {owner.email} | Mobile: {owner.mobile}")

if __name__ == "__main__":
    asyncio.run(list_owners())
