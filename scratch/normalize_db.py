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
import numpy as np
from face_service import l2_normalize

async def normalize_all():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RegisteredFace))
        faces = result.scalars().all()
        
        updated_count = 0
        for face in faces:
            emb = np.array(face.face_encoding, dtype=np.float32)
            norm = np.linalg.norm(emb)
            if abs(norm - 1.0) > 0.01: # Only update if not already normalized
                normalized_emb = l2_normalize(emb).tolist()
                face.face_encoding = normalized_emb
                updated_count += 1
                
        if updated_count > 0:
            await session.commit()
            print(f"Successfully normalized {updated_count} faces in the database.")
        else:
            print("All faces are already normalized.")

asyncio.run(normalize_all())
