import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if "postgres" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
from models import RegisteredFace

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RegisteredFace).order_by(RegisteredFace.id.desc()).limit(10))
        faces = result.scalars().all()
        
        print(f"Total recent faces: {len(faces)}")
        if len(faces) < 2:
            return
            
        print("\nDistances between recent faces:")
        import numpy as np
        
        for i in range(len(faces)):
            emb1 = np.array(faces[i].face_encoding)
            print(f"[{faces[i].id}] {faces[i].name} (Role: {faces[i].role}) - L2 Norm: {np.linalg.norm(emb1):.4f}")
            for j in range(i+1, len(faces)):
                emb2 = np.array(faces[j].face_encoding)
                l2_dist = np.linalg.norm(emb1 - emb2)
                print(f"  -> Distance to [{faces[j].id}] {faces[j].name}: {l2_dist:.4f}")

asyncio.run(check())
