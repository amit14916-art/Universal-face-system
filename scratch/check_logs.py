import asyncio
from database import AsyncSessionLocal
from models import AttendanceLog, RegisteredFace
from sqlalchemy.future import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AttendanceLog, RegisteredFace.name)
            .join(RegisteredFace, AttendanceLog.face_id == RegisteredFace.id)
            .order_by(AttendanceLog.timestamp.desc())
            .limit(10)
        )
        logs = result.all()
        if not logs:
            print("No activity logs found yet.")
        else:
            print("--- Recent Activity Logs ---")
            for log, name in logs:
                print(f"[{log.timestamp}] Detected: {name} (ID: {log.face_id})")

if __name__ == "__main__":
    asyncio.run(check())
