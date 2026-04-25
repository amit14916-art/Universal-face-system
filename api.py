import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uvicorn
import asyncio
import time

from database import AsyncSessionLocal, init_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from models import RegisteredFace, AttendanceLog, GymOwner
import face_service
import main as engine # Integrated with the Sentinel Engine
import base64
import numpy as np
import cv2
from pydantic import BaseModel
from supabase import create_client, Client

# Supabase Storage Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "face"

class RegisterRequest(BaseModel):
    owner_id: int
    name: str
    role: str
    image_base64: str


class RenameRequest(BaseModel):
    name: str

class BlacklistRequest(BaseModel):
    is_blacklisted: bool

class NodeRequest(BaseModel):
    name: str
    url: str
    owner_id: int

class AuthRequest(BaseModel):
    identifier: str
    password: str

class SignupRequest(BaseModel):
    gym_name: str
    email: str
    mobile: str
    password: str

class NotificationSettingsRequest(BaseModel):
    owner_id: int
    webhook_url: str
    notify_on_entry: bool
    notify_on_expiry: bool

class SubscriptionRequest(BaseModel):
    user_id: int
    expiry_date: str # ISO format
    plan_type: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure static directories exist to prevent deployment crashes
    os.makedirs("static/faces", exist_ok=True)
    os.makedirs("frontend/dist/assets", exist_ok=True)
    
    logger.info("SYSTEM: Initializing Database Connection...")
    await init_db()
    logger.info("SYSTEM: Database Connection Established")


    
    # Initialize Sentinel Engine inside API process for shared memory
    engine.start_background_workers()
    
    # Skip starting local camera by default on cloud environment
    # sources = [
    #     {"id": 0, "name": "Main_Hub", "rotation": None}
    # ]
    # 
    # for src in sources:
    #     node = engine.SentinelNode(src["id"], src["name"], rotation=src["rotation"])
    #     node.start()
    #     engine.global_nodes[src["name"]] = node
    
    print(">> Sentinel Engine Integrated & Online")
    yield
    # Clean shutdown
    for node_name, node in engine.global_nodes.items():
        node.stop()

app = FastAPI(title="Universal Face System API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

# Enable CORS for frontend integration
origins = os.getenv("CORS_ORIGINS", "*").split(",")
origins = [o.strip() for o in origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"INCOMING: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"OUTGOING: {request.method} {request.url} -> {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"CRASH: {request.method} {request.url} -> {e}")
        raise

# Dependency to get DB session safely
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# --- LIVE STREAMING CORE ---
def gen_frames(node_name: str):
    """MJPEG frame generator for a specific Sentinel node."""
    while True:
        if node_name in engine.global_nodes:
            node = engine.global_nodes[node_name]
            frame = node.last_frame
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.04) # ~25 FPS max

@app.get("/api/stream/{node_name}")
async def stream_node(node_name: str):
    if node_name not in engine.global_nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    return StreamingResponse(gen_frames(node_name), media_type='multipart/x-mixed-replace; boundary=frame')

@app.get("/api/telemetry")
async def get_system_telemetry():
    return engine.get_telemetry()

@app.post("/api/nodes/add")
async def add_node(request: NodeRequest):
    if request.name in engine.global_nodes:
        logger.info(f"Stopping existing node: {request.name}")
        engine.global_nodes[request.name].stop()
        await asyncio.sleep(1) # Give it a second to release the camera
        
    try:
        url = int(request.url) if request.url.isdigit() else request.url
        if isinstance(url, str) and url.startswith("http"):
            # Auto-append /video if user forgets it for IP Webcam
            if url.count('/') < 3 or (url.count('/') == 3 and url.endswith('/')):
                url = url.rstrip('/') + '/video'

        node = engine.SentinelNode(url, request.name, owner_id=request.owner_id, rotation=None)
        node.start()
        engine.global_nodes[request.name] = node
        return {"message": f"Node {request.name} added successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/signup")
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(GymOwner).where(GymOwner.email == request.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_owner = GymOwner(
        gym_name=request.gym_name,
        email=request.email,
        mobile=request.mobile,
        password=request.password
    )
    db.add(new_owner)
    await db.commit()
    return {"message": "Account created successfully", "status": "success"}

@app.post("/api/auth/login")
async def login(request: AuthRequest, db: AsyncSession = Depends(get_db)):
    # Match either email or mobile number
    from sqlalchemy import or_
    result = await db.execute(
        select(GymOwner).where(
            or_(
                GymOwner.email == request.identifier,
                GymOwner.mobile == request.identifier
            )
        )
    )
    owner = result.scalars().first()
    
    if not owner or owner.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "message": "Login successful", 
        "status": "success", 
        "owner_id": owner.id,
        "gym_name": owner.gym_name
    }

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/faces", StaticFiles(directory="static/faces"), name="faces")
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/")
async def root():
    return FileResponse("frontend/dist/index.html")

@app.get("/api/users")
async def get_users(owner_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.owner_id == owner_id))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "owner_id": u.owner_id,
            "name": u.name,
            "role": u.role,
            "image_path": u.image_path,
            "is_blacklisted": u.is_blacklisted,
            "subscription_expiry": u.subscription_expiry,
            "plan_type": u.plan_type,
            "notes": u.notes,
            "created_at": u.created_at,
            "is_active": u.is_active
        } for u in users
    ]

@app.get("/api/logs")
async def get_logs(owner_id: int, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    query = (
        select(AttendanceLog, RegisteredFace.name, RegisteredFace.role, RegisteredFace.image_path, RegisteredFace.subscription_expiry)
        .join(RegisteredFace, AttendanceLog.face_id == RegisteredFace.id)
        .where(AttendanceLog.owner_id == owner_id)
        .order_by(AttendanceLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    logs = []
    for row in result.all():
        log, name, role, img_path, expiry = row
        from datetime import datetime
        is_expired = expiry < datetime.now() if expiry else False
        logs.append({
            "id": log.id,
            "face_id": log.face_id,
            "name": name,
            "role": role,
            "image_path": img_path,
            "subscription_status": "expired" if is_expired else "active",
            "timestamp": log.timestamp,
            "location": log.location
        })
    return logs

@app.get("/api/stats")
async def get_stats(owner_id: int, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # 1. Member Stats
    total_q = await db.execute(select(func.count(RegisteredFace.id)).where(RegisteredFace.owner_id == owner_id))
    total_members = total_q.scalar()

    active_q = await db.execute(select(func.count(RegisteredFace.id)).where(
        RegisteredFace.owner_id == owner_id,
        RegisteredFace.subscription_expiry > now
    ))
    active_members = active_q.scalar()

    # 2. Today's Attendance
    today_q = await db.execute(select(func.count(AttendanceLog.id)).where(
        AttendanceLog.owner_id == owner_id,
        AttendanceLog.timestamp >= today_start
    ))
    today_count = today_q.scalar()

    # 3. Weekly Trend (Last 7 Days)
    weekly_trend = []
    for i in range(7):
        d_start = today_start - timedelta(days=6-i)
        d_end = d_start + timedelta(days=1)
        q = await db.execute(select(func.count(AttendanceLog.id)).where(
            AttendanceLog.owner_id == owner_id,
            AttendanceLog.timestamp >= d_start,
            AttendanceLog.timestamp < d_end
        ))
        weekly_trend.append({
            "day": d_start.strftime("%a"),
            "count": q.scalar()
        })

    # 4. Peak Hours Distribution (Today)
    peak_hours = []
    for h in range(6, 23): # From 6 AM to 10 PM
        h_start = today_start.replace(hour=h)
        h_end = h_start + timedelta(hours=1)
        q = await db.execute(select(func.count(AttendanceLog.id)).where(
            AttendanceLog.owner_id == owner_id,
            AttendanceLog.timestamp >= h_start,
            AttendanceLog.timestamp < h_end
        ))
        peak_hours.append({
            "hour": f"{h:02d}:00",
            "count": q.scalar()
        })

    return {
        "summary": {
            "total_members": total_members,
            "active_members": active_members,
            "expired_members": total_members - active_members,
            "today_attendance": today_count
        },
        "weekly_trend": weekly_trend,
        "peak_hours": peak_hours
    }

@app.put("/api/users/subscription")
async def update_subscription(request: SubscriptionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RegisteredFace).where(RegisteredFace.id == request.user_id))
    user = result.scalars().first()
    if not user: raise HTTPException(status_code=404, detail="Member not found")
    
    from datetime import datetime
    try:
        user.subscription_expiry = datetime.fromisoformat(request.expiry_date.replace("Z", "+00:00"))
        user.plan_type = request.plan_type
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid date format")
        
    return {"message": "Subscription updated successfully"}

@app.put("/api/settings/notifications")
async def update_notification_settings(request: NotificationSettingsRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GymOwner).where(GymOwner.id == request.owner_id))
    owner = result.scalars().first()
    if not owner: raise HTTPException(status_code=404, detail="Owner not found")
    
    owner.webhook_url = request.webhook_url
    owner.notify_on_entry = request.notify_on_entry
    owner.notify_on_expiry = request.notify_on_expiry
    
    await db.commit()
    return {"message": "Notification settings updated"}

@app.get("/api/settings/notifications")
async def get_notification_settings(owner_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GymOwner).where(GymOwner.id == owner_id))
    owner = result.scalars().first()
    if not owner: raise HTTPException(status_code=404, detail="Owner not found")
    
    return {
        "webhook_url": owner.webhook_url,
        "notify_on_entry": owner.notify_on_entry,
        "notify_on_expiry": owner.notify_on_expiry
    }

@app.get("/api/stats/hourly")
async def get_hourly_stats(db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta
    yesterday = datetime.now() - timedelta(days=1)
    result = await db.execute(
        select(AttendanceLog.timestamp).where(AttendanceLog.timestamp >= yesterday)
    )
    from collections import Counter
    ts_list = result.scalars().all()
    hours = [ts.hour for ts in ts_list]
    counts = Counter(hours)
    
    current_hour = datetime.now().hour
    data = []
    for i in range(12):
        h = (current_hour - i) % 24
        data.append({"hour": f"{h}:00", "count": counts.get(h, 0)})
    
    # Add unique visitor count
    res_unique = await db.execute(
        select(RegisteredFace.id).where(RegisteredFace.is_active == True)
    )
    unique_count = len(res_unique.scalars().all())
    
    return {"hourly": data[::-1], "unique_captured": unique_count}

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

        # Detect and get embedding using SOTA ArcFace
        objs = face_service.extract_face(frame, enforce_liveness=False)
        
        if not objs:
            raise HTTPException(status_code=400, detail="No face detected in image")
        
        if len(objs) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected. Please provide a clear image of one face.")

        raw_emb = np.array(objs[0]["embedding"], dtype=np.float32)
        encoding = face_service.l2_normalize(raw_emb).tolist()
        
        # Check if user already exists
        result = await db.execute(select(RegisteredFace).where(RegisteredFace.name == request.name))
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="User already exists")

        # Save to DB as pure vector
        new_face = RegisteredFace(
            owner_id=request.owner_id,
            name=request.name,
            role=request.role,
            face_encoding=encoding
        )
        db.add(new_face)
        await db.commit()
        await db.refresh(new_face)

        # Cloud Storage Upload (Supabase Bucket)
        filename = f"{int(time.time())}_{new_face.id}.jpg"
        file_path = f"registration/{filename}"
        
        # Convert frame to bytes for upload
        _, img_encoded = cv2.imencode('.jpg', frame)
        img_bytes = img_encoded.tobytes()

        try:
            # Upload to Supabase 'face' bucket
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=img_bytes,
                file_options={"content-type": "image/jpeg"}
            )
            
            # Get Public URL
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            
            # Update user record with the Cloud URL
            new_face.image_path = public_url
            await db.commit()
            logger.info(f"Photo uploaded to cloud: {public_url}")
            
        except Exception as storage_err:
            logger.error(f"Cloud Storage Error: {storage_err}")
            # Fallback to local if cloud fails (optional)
            local_path = f"static/faces/{filename}"
            cv2.imwrite(local_path, frame)
            new_face.image_path = local_path
            await db.commit()
        
        return {"message": f"Successfully registered {request.name}", "status": "success", "image_url": new_face.image_path}

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

