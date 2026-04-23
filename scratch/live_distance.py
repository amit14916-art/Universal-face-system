import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os
from dotenv import load_dotenv
import numpy as np

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
        result = await session.execute(select(RegisteredFace).order_by(RegisteredFace.id.desc()).limit(5))
        recent_faces = result.scalars().all()
        
        result2 = await session.execute(select(RegisteredFace).where(RegisteredFace.name == 'AMIT KUMAR').limit(1))
        amit = result2.scalars().first()
        
        if not amit:
            print("AMIT KUMAR not found in database!")
            return
            
        print(f"AMIT KUMAR found (ID: {amit.id}). L2 Norm: {np.linalg.norm(np.array(amit.face_encoding)):.4f}")
        
        print("\nDistances from recent visitors to AMIT KUMAR:")
        amit_emb = np.array(amit.face_encoding, dtype=np.float32)
        
        for face in recent_faces:
            emb = np.array(face.face_encoding, dtype=np.float32)
            dist = np.linalg.norm(amit_emb - emb)
            norm = np.linalg.norm(emb)
            print(f"[{face.id}] {face.name} | Norm: {norm:.4f} | Distance to AMIT: {dist:.4f}")

asyncio.run(check())
