from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uvicorn

from database import AsyncSessionLocal, init_db
from models import RegisteredFace, AttendanceLog
import face_service
import base64
import numpy as np
import cv2
from pydantic import BaseModel

class RegisterRequest(BaseModel):
    name: str
    role: str
    image_base64: str

class RenameRequest(BaseModel):
    name: str

class BlacklistRequest(BaseModel):
    is_blacklisted: bool

app = FastAPI(title="Universal Face System API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.on_event("startup")
async def startup_event():
    await init_db()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/faces", StaticFiles(directory="static/faces"), name="faces")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace))
    users = result.scalars().all()
    # Exclude binary encoding from JSON response
    return [
        {
            "id": u.id,
            "name": u.name,
            "role": u.role,
            "image_path": u.image_path,
            "is_blacklisted": u.is_blacklisted,
            "notes": u.notes,
            "created_at": u.created_at,
            "is_active": u.is_active
        } for u in users
    ]

@app.get("/api/logs")
async def get_logs(db: AsyncSession = Depends(get_db), limit: int = 50):
    # Join with RegisteredFace to get names
    query = (
        select(AttendanceLog, RegisteredFace.name, RegisteredFace.role, RegisteredFace.image_path)
        .join(RegisteredFace, AttendanceLog.face_id == RegisteredFace.id)
        .order_by(AttendanceLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    logs = []
    for row in result.all():
        log, name, role, img_path = row
        # Also check if they are blacklisted now
        logs.append({
            "id": log.id,
            "face_id": log.face_id,
            "name": name,
            "role": role,
            "image_path": img_path,
            "timestamp": log.timestamp,
            "location": log.location
        })
    return logs

@app.get("/api/stats/hourly")
async def get_hourly_stats(db: AsyncSession = Depends(get_db)):
    # Simple count of entries in the last 24 hours grouped by hour
    from datetime import datetime, timedelta
    yesterday = datetime.now() - timedelta(days=1)
    result = await db.execute(
        select(AttendanceLog.timestamp).where(AttendanceLog.timestamp >= yesterday)
    )
    from collections import Counter
    hours = [ts.hour for ts in result.scalars().all()]
    counts = Counter(hours)
    # Return 24 hours
    current_hour = datetime.now().hour
    data = []
    for i in range(24):
        h = (current_hour - i) % 24
        data.append({"hour": f"{h}:00", "count": counts.get(h, 0)})
    return data[::-1] # chronological

@app.put("/api/users/{user_id}/rename")
async def rename_user(user_id: int, request: RenameRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.name = request.name
    await db.commit()
    return {"message": "User renamed successfully"}

@app.put("/api/users/{user_id}/blacklist")
async def toggle_blacklist(user_id: int, request: BlacklistRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.is_blacklisted = request.is_blacklisted
    await db.commit()
    return {"message": "Blacklist status updated"}

@app.post("/api/register")
async def register_user(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Decode base64 image
        header, encoded = request.image_base64.split(",", 1) if "," in request.image_base64 else (None, request.image_base64)
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")

        # Detect and get embedding
        face_locations, face_encodings = await face_service.get_face_embeddings(frame)

        if not face_encodings:
            raise HTTPException(status_code=400, detail="No face detected in image")
        
        if len(face_encodings) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected. Please provide a clear image of one face.")

        encoding = face_encodings[0]
        
        # Check if user already exists
        result = await db.execute(select(RegisteredFace).where(RegisteredFace.name == request.name))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="User already exists")

        # Save to DB
        new_face = RegisteredFace(
            name=request.name,
            role=request.role,
            face_encoding=encoding
        )
        db.add(new_face)
        await db.commit()
        
        return {"message": f"Successfully registered {request.name}", "status": "success"}

    except Exception as e:
        print(f"Registration Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return {"message": f"User {user_id} deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
